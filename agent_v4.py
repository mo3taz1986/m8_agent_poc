import json
import os
from datetime import datetime

import numpy as np
from anthropic import Anthropic
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import (
    ROOT_DIR,
    OUTPUT_DIR,
    LOG_FILE,
    CHUNK_RECORDS_FILE,
    CHUNK_EMBEDDINGS_FILE,
    EMBEDDING_MODEL_NAME,
    CLAUDE_MODEL_NAME,
    TOP_K,
    SIMILARITY_THRESHOLD,
)

load_dotenv(dotenv_path=ROOT_DIR / ".env")

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in .env")

client = Anthropic(api_key=api_key)

# Load embedding model once and reuse it
embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def load_index():
    if not CHUNK_RECORDS_FILE.exists() or not CHUNK_EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(
            "Index files not found. Run build_index.py first."
        )

    with CHUNK_RECORDS_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    embeddings = np.load(CHUNK_EMBEDDINGS_FILE)
    return records, embeddings


def retrieve_top_chunks(question, records, embeddings, embedding_model, top_k=3):
    question_embedding = embedding_model.encode([question], convert_to_numpy=True)
    scores = cosine_similarity(question_embedding, embeddings)[0]

    scored_records = []
    for record, score in zip(records, scores):
        row = record.copy()
        row["score"] = float(score)
        scored_records.append(row)

    scored_records.sort(key=lambda x: x["score"], reverse=True)
    return scored_records[:top_k]


def should_answer(retrieved_chunks):
    if not retrieved_chunks:
        return False
    return retrieved_chunks[0]["score"] >= SIMILARITY_THRESHOLD


def ask_claude(question, retrieved_chunks):
    context = "\n\n".join(
        [
            f"Source: {chunk['doc_name']} | Chunk {chunk['chunk_id']} | Score: {chunk['score']:.4f}\n{chunk['text']}"
            for chunk in retrieved_chunks
        ]
    )

    prompt = f"""
You are a governance and policy assistant.

Rules:
1. Use ONLY the retrieved context below.
2. If the answer is not clearly supported, say:
   "I do not have enough evidence from the retrieved context."
3. If the question is ambiguous, ask one clarifying question.
4. Cite the exact supporting sentence.
5. Mention the source document name in your answer.
6. Keep the answer concise and grounded.

Retrieved context:
{context}

Question:
{question}
"""

    response = client.messages.create(
        model=CLAUDE_MODEL_NAME,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def log_interaction(question, retrieved_chunks, answer, answered):
    OUTPUT_DIR.mkdir(exist_ok=True)

    row = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "question": question,
        "answered": answered,
        "top_chunks": retrieved_chunks,
        "answer": answer,
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def process_question(question: str):
    """Reusable function for chatbot and other interfaces."""
    records, embeddings = load_index()

    retrieved_chunks = retrieve_top_chunks(
        question, records, embeddings, embedding_model, top_k=TOP_K
    )

    if not should_answer(retrieved_chunks):
        answer = "I do not have enough evidence from the retrieved context."
        answered = False
    else:
        answer = ask_claude(question, retrieved_chunks)
        answered = True

    log_interaction(question, retrieved_chunks, answer, answered)

    return {
        "question": question,
        "answer": answer,
        "answered": answered,
        "retrieved_chunks": retrieved_chunks,
    }


def main():
    print("Governance Retrieval Agent V4")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("Ask: ").strip()
        if question.lower() == "exit":
            print("Goodbye.")
            break

        if not question:
            print("Please enter a question.\n")
            continue

        result = process_question(question)

        print("\nTop retrieved chunks:")
        for chunk in result["retrieved_chunks"]:
            print(
                f"- {chunk['doc_name']} | chunk {chunk['chunk_id']} | score={chunk['score']:.4f}"
            )

        print(f"\nAnswer:\n{result['answer']}\n")


if __name__ == "__main__":
    main()