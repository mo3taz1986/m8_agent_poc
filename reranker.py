import re
from typing import Dict, List


def tokenize(text: str) -> List[str]:
    """
    Simple lowercase tokenization for reranking features.
    """
    return re.findall(r"\b\w+\b", text.lower())


def compute_term_coverage(question: str, chunk_text: str) -> float:
    """
    Score how much of the question vocabulary is covered by the chunk.
    Returns a value between 0 and 1.
    """
    question_tokens = set(tokenize(question))
    chunk_tokens = set(tokenize(chunk_text))

    if not question_tokens:
        return 0.0

    overlap = question_tokens.intersection(chunk_tokens)
    return len(overlap) / len(question_tokens)


def rerank_chunks(
    question: str,
    candidate_chunks: List[Dict],
    hybrid_weight: float = 0.7,
    term_coverage_weight: float = 0.3,
) -> List[Dict]:
    """
    Rerank retrieved chunks using:
    - hybrid retrieval score
    - question term coverage in the chunk text

    Final rerank score is a weighted blend.
    """
    reranked = []

    for chunk in candidate_chunks:
        row = chunk.copy()
        term_coverage = compute_term_coverage(question, row.get("text", ""))
        row["term_coverage_score"] = float(term_coverage)

        hybrid_score = float(row.get("hybrid_score", 0.0))
        row["rerank_score"] = (
            hybrid_weight * hybrid_score
            + term_coverage_weight * term_coverage
        )
        reranked.append(row)

    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    return reranked