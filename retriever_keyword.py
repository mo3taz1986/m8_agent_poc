import json
import re
from typing import List, Dict

from rank_bm25 import BM25Okapi

from src.config import CHUNK_RECORDS_FILE, BM25_INDEX_FILE


def tokenize(text: str) -> List[str]:
    """
    Tokenize user query or corpus text for keyword retrieval.
    """
    return re.findall(r"\b\w+\b", text.lower())


def load_keyword_index():
    """
    Load chunk records and tokenized BM25 corpus, then construct BM25 retriever.
    """
    if not CHUNK_RECORDS_FILE.exists():
        raise FileNotFoundError(
            f"Chunk records file not found: {CHUNK_RECORDS_FILE}"
        )

    if not BM25_INDEX_FILE.exists():
        raise FileNotFoundError(
            f"BM25 corpus file not found: {BM25_INDEX_FILE}. Run build_keyword_index first."
        )

    with CHUNK_RECORDS_FILE.open("r", encoding="utf-8") as f:
        records = json.load(f)

    with BM25_INDEX_FILE.open("r", encoding="utf-8") as f:
        tokenized_corpus = json.load(f)

    bm25 = BM25Okapi(tokenized_corpus)
    return records, bm25


def retrieve_keyword_chunks(question: str, top_k: int = 5) -> List[Dict]:
    """
    Retrieve top matching chunks using BM25.
    """
    records, bm25 = load_keyword_index()
    query_tokens = tokenize(question)

    scores = bm25.get_scores(query_tokens)

    scored_records = []
    for record, score in zip(records, scores):
        row = record.copy()
        row["keyword_score"] = float(score)
        scored_records.append(row)

    scored_records.sort(key=lambda x: x["keyword_score"], reverse=True)
    return scored_records[:top_k]