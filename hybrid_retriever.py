from typing import Dict, List, Tuple

from src.config import (
    FINAL_TOP_K,
    HYBRID_TOP_K,
    HYBRID_WEIGHT,
    KEYWORD_TOP_K,
    KEYWORD_WEIGHT,
    SEMANTIC_TOP_K,
    SEMANTIC_WEIGHT,
    TERM_COVERAGE_WEIGHT,
)
from src.retriever_keyword import retrieve_keyword_chunks
from src.retriever_semantic import retrieve_semantic_chunks
from src.reranker import rerank_chunks


def normalize_scores(records: List[Dict], score_key: str, normalized_key: str) -> List[Dict]:
    """
    Min-max normalize a score field to the range [0, 1].
    If all scores are equal, assign 1.0 to all non-empty records.
    """
    if not records:
        return records

    scores = [float(record.get(score_key, 0.0)) for record in records]
    min_score = min(scores)
    max_score = max(scores)

    for record in records:
        raw_score = float(record.get(score_key, 0.0))
        if max_score == min_score:
            record[normalized_key] = 1.0
        else:
            record[normalized_key] = (raw_score - min_score) / (max_score - min_score)

    return records


def chunk_unique_key(record: Dict) -> Tuple:
    """
    Unique chunk identity across retrieval methods.
    """
    return (
        record.get("doc_name"),
        record.get("section_id"),
        record.get("chunk_id"),
    )


def merge_results(
    semantic_results: List[Dict],
    keyword_results: List[Dict],
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> List[Dict]:
    """
    Merge semantic and keyword retrieval results into one ranked list.
    """
    semantic_results = normalize_scores(
        semantic_results,
        score_key="semantic_score",
        normalized_key="semantic_score_norm",
    )
    keyword_results = normalize_scores(
        keyword_results,
        score_key="keyword_score",
        normalized_key="keyword_score_norm",
    )

    merged = {}

    for record in semantic_results:
        key = chunk_unique_key(record)
        merged[key] = record.copy()
        merged[key].setdefault("keyword_score", 0.0)
        merged[key].setdefault("keyword_score_norm", 0.0)
        merged[key]["hybrid_score"] = (
            semantic_weight * merged[key].get("semantic_score_norm", 0.0)
            + keyword_weight * merged[key].get("keyword_score_norm", 0.0)
        )

    for record in keyword_results:
        key = chunk_unique_key(record)
        if key not in merged:
            merged[key] = record.copy()
            merged[key].setdefault("semantic_score", 0.0)
            merged[key].setdefault("semantic_score_norm", 0.0)
        else:
            merged[key]["keyword_score"] = record.get("keyword_score", 0.0)
            merged[key]["keyword_score_norm"] = record.get("keyword_score_norm", 0.0)

        merged[key]["hybrid_score"] = (
            semantic_weight * merged[key].get("semantic_score_norm", 0.0)
            + keyword_weight * merged[key].get("keyword_score_norm", 0.0)
        )

    merged_results = list(merged.values())
    merged_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return merged_results


def retrieve_hybrid_chunks(
    question: str,
    semantic_top_k: int = SEMANTIC_TOP_K,
    keyword_top_k: int = KEYWORD_TOP_K,
    hybrid_top_k: int = HYBRID_TOP_K,
    final_top_k: int = FINAL_TOP_K,
    semantic_weight: float = SEMANTIC_WEIGHT,
    keyword_weight: float = KEYWORD_WEIGHT,
    hybrid_weight: float = HYBRID_WEIGHT,
    term_coverage_weight: float = TERM_COVERAGE_WEIGHT,
) -> List[Dict]:
    """
    Run semantic retrieval + keyword retrieval, merge them,
    then rerank final candidates.
    """
    semantic_results = retrieve_semantic_chunks(question, top_k=semantic_top_k)
    keyword_results = retrieve_keyword_chunks(question, top_k=keyword_top_k)

    merged_results = merge_results(
        semantic_results=semantic_results,
        keyword_results=keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
    )

    candidate_chunks = merged_results[:hybrid_top_k]

    reranked_results = rerank_chunks(
        question=question,
        candidate_chunks=candidate_chunks,
        hybrid_weight=hybrid_weight,
        term_coverage_weight=term_coverage_weight,
    )

    return reranked_results[:final_top_k]