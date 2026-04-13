import json
import os
from datetime import datetime, timezone
from typing import Dict, List

from anthropic import Anthropic
from dotenv import load_dotenv

from src.config import (
    ROOT_DIR,
    OUTPUT_DIR,
    LOG_FILE,
    CLAUDE_MODEL_NAME,
    MAX_CONTEXT_CHUNKS,
    MIN_HYBRID_SCORE_TO_ANSWER,
    MIN_RERANK_SCORE_TO_ANSWER,
    ENABLE_GROUNDING_CHECK,
    MIN_GROUNDING_SCORE_TO_ACCEPT,
)
from src.grounding_check import verify_grounding
from src.hybrid_retriever import retrieve_hybrid_chunks

load_dotenv(dotenv_path=ROOT_DIR / ".env")

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in .env")

client = Anthropic(api_key=api_key)


def build_context(retrieved_chunks: List[Dict], max_chunks: int = MAX_CONTEXT_CHUNKS) -> str:
    """
    Build grounded context for the LLM from the top retrieved chunks.
    """
    selected_chunks = retrieved_chunks[:max_chunks]

    context_parts = []
    for chunk in selected_chunks:
        context_parts.append(
            (
                f"Source: {chunk['doc_name']} | "
                f"Section: {chunk.get('section_title', 'General')} | "
                f"Section ID: {chunk.get('section_id', 0)} | "
                f"Chunk ID: {chunk['chunk_id']} | "
                f"Semantic Score: {chunk.get('semantic_score', 0.0):.4f} | "
                f"Keyword Score: {chunk.get('keyword_score', 0.0):.4f} | "
                f"Hybrid Score: {chunk.get('hybrid_score', 0.0):.4f} | "
                f"Rerank Score: {chunk.get('rerank_score', 0.0):.4f}\n"
                f"{chunk['text']}"
            )
        )

    return "\n\n".join(context_parts)


def should_answer(retrieved_chunks: List[Dict]) -> bool:
    """
    Decide whether the evidence is strong enough to answer.
    """
    if not retrieved_chunks:
        return False

    top_chunk = retrieved_chunks[0]
    top_hybrid_score = float(top_chunk.get("hybrid_score", 0.0))
    top_rerank_score = float(top_chunk.get("rerank_score", 0.0))

    if top_hybrid_score < MIN_HYBRID_SCORE_TO_ANSWER:
        return False

    if top_rerank_score < MIN_RERANK_SCORE_TO_ANSWER:
        return False

    return True


def ask_claude(question: str, retrieved_chunks: List[Dict]) -> str:
    """
    Generate a grounded answer using only retrieved context.
    """
    context = build_context(retrieved_chunks)

    prompt = f"""
You are a governance and policy assistant.

Rules:
1. Use ONLY the retrieved context below.
2. Do not use outside knowledge.
3. If the answer is not clearly supported by the retrieved context, say exactly:
I do not have enough evidence from the retrieved context.
4. Start with a direct answer in one sentence.
5. Then provide a short evidence section.
6. Quote only short supporting snippets, not long passages.
7. Mention the source document name and section title.
8. If the question is ambiguous, ask one short clarifying question instead of guessing.
9. Do not invent policy owners, timelines, controls, or actions that are not in the context.

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


def log_interaction(
    question: str,
    retrieved_chunks: List[Dict],
    answer: str,
    answered: bool,
    grounding_result: Dict,
) -> None:
    """
    Log the full interaction in JSONL format for later evaluation.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    top_chunk = retrieved_chunks[0] if retrieved_chunks else {}

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answered": answered,
        "top_chunk_hybrid_score": float(top_chunk.get("hybrid_score", 0.0)),
        "top_chunk_rerank_score": float(top_chunk.get("rerank_score", 0.0)),
        "grounding_score": grounding_result.get("grounding_score", 0.0),
        "grounding_verdict": grounding_result.get("grounding_verdict", "unknown"),
        "top_chunks": retrieved_chunks,
        "answer": answer,
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def process_question(question: str) -> Dict:
    """
    Main reusable V5 question-processing function.
    """
    retrieved_chunks = retrieve_hybrid_chunks(question)

    if not should_answer(retrieved_chunks):
        answer = "I do not have enough evidence from the retrieved context."
        answered = False
        grounding_result = {
            "grounding_score": 1.0,
            "grounding_verdict": "refused_pre_answer",
            "grounded": True,
        }
    else:
        answer = ask_claude(question, retrieved_chunks)
        answered = True

        if ENABLE_GROUNDING_CHECK:
            grounding_result = verify_grounding(
                answer=answer,
                retrieved_chunks=retrieved_chunks,
                min_grounding_score=MIN_GROUNDING_SCORE_TO_ACCEPT,
            )

            if not grounding_result["grounded"]:
                answer = "I do not have enough evidence from the retrieved context."
                answered = False
                grounding_result["grounding_verdict"] = "downgraded_to_refusal"
        else:
            grounding_result = {
                "grounding_score": None,
                "grounding_verdict": "disabled",
                "grounded": True,
            }

    log_interaction(
        question=question,
        retrieved_chunks=retrieved_chunks,
        answer=answer,
        answered=answered,
        grounding_result=grounding_result,
    )

    return {
        "question": question,
        "answer": answer,
        "answered": answered,
        "retrieved_chunks": retrieved_chunks,
        "grounding": grounding_result,
    }


def main():
    print("Governance Retrieval Agent V5")
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
                f"- {chunk['doc_name']} | "
                f"section={chunk.get('section_title', 'General')} | "
                f"chunk={chunk['chunk_id']} | "
                f"hybrid={chunk.get('hybrid_score', 0.0):.4f} | "
                f"rerank={chunk.get('rerank_score', 0.0):.4f}"
            )

        print(
            f"\nGrounding:"
            f" verdict={result['grounding'].get('grounding_verdict')} | "
            f"score={result['grounding'].get('grounding_score')}"
        )

        print(f"\nAnswer:\n{result['answer']}\n")


if __name__ == "__main__":
    main()
