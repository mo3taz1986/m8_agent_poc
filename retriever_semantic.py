import json
from typing import List, Dict

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import (
    CHUNK_RECORDS_FILE,
    CHUNK_EMBEDDINGS_FILE,
    EMBEDDING_MODEL_NAME,
)


_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """
    Load the embedding model once and reuse it.
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def load_semantic_index():
    """
    Load chunk records and precomputed embeddings.
    """
    if not CHUNK_RECORDS_FILE.exists():
        raise FileNotFoundError(
            f"Chunk records file not found: {CHUNK_RECORDS_FILE}"
        )

    if not CHUNK_EMBEDDINGS_FILE.exists():
        raise FileNotFoundError(
            f"Chunk embeddings file not found: {CHUNK_EMBEDDINGS_FILE}. Run build_index first."
        )

    with CHUNK_RECORDS_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    embeddings = np.load(CHUNK_EMBEDDINGS_FILE)
    return records, embeddings


def retrieve_semantic_chunks(question: str, top_k: int = 5) -> List[Dict]:
    """
    Retrieve top matching chunks using embedding similarity.
    """
    records, embeddings = load_semantic_index()
    embedding_model = get_embedding_model()

    question_embedding = embedding_model.encode([question], convert_to_numpy=True)
    scores = cosine_similarity(question_embedding, embeddings)[0]

    scored_records = []
    for record, score in zip(records, scores):
        row = record.copy()
        row["semantic_score"] = float(score)
        scored_records.append(row)

    scored_records.sort(key=lambda x: x["semantic_score"], reverse=True)
    return scored_records[:top_k]