from __future__ import annotations

from typing import Dict, List, Optional

from src.config import (
    MAX_CONTEXT_CHUNKS,
    MIN_HYBRID_SCORE_TO_ANSWER,
    MIN_RERANK_SCORE_TO_ANSWER,
)
from src.hybrid_retriever import retrieve_hybrid_chunks


class ContextAgent:
    """
    Retrieval and context enrichment specialist.

    Owns:
    - Running hybrid retrieval (semantic + BM25 + reranking)
    - Evaluating whether retrieved evidence is sufficient to answer
    - Formatting chunks into the LLM context string
    - Mapping chunks to source citations

    Does NOT own:
    - Generating answers (answer_service.py)
    - Routing decisions (leader_agent.py)
    - Grounding verification (grounding_check.py)
    - Concept/definition answering (concept_answer_service.py)

    Called by the Leader (via graph state) and by answer_service.
    Returns a structured result dict — does not call LLMs.
    """

    def retrieve(self, question: str, top_k: int = 4) -> Dict:
        """
        Run hybrid retrieval for a question and return a structured
        context result that answer_service can use directly.

        Parameters
        ----------
        question : str
            The user question or requirement context string.
        top_k : int
            Maximum number of chunks to include in context_string.

        Returns
        -------
        Dict with keys:
            chunks            — full list of retrieved + reranked chunks
            sources           — citation-ready source list (top_k chunks)
            context_string    — formatted string ready for LLM prompt injection
            sufficient        — bool, True if retrieval quality meets threshold
            retrieval_quality — "sufficient" | "insufficient" | "empty"
            top_hybrid_score  — float, highest hybrid score in results
            top_rerank_score  — float, highest rerank score in results
        """
        chunks = retrieve_hybrid_chunks(question)

        if not chunks:
            return self._empty_result()

        top_hybrid = float(chunks[0].get("hybrid_score", 0.0))
        top_rerank = float(chunks[0].get("rerank_score", 0.0))
        sufficient  = self._is_sufficient(chunks)

        return {
            "chunks":           chunks,
            "sources":          self._map_sources(chunks[:top_k]),
            "context_string":   self._build_context_string(chunks, max_chunks=top_k),
            "sufficient":       sufficient,
            "retrieval_quality": "sufficient" if sufficient else "insufficient",
            "top_hybrid_score": top_hybrid,
            "top_rerank_score": top_rerank,
        }

    # ── Private helpers ────────────────────────────────────────────────────

    @staticmethod
    def _is_sufficient(chunks: List[Dict]) -> bool:
        """
        Evaluate whether the top retrieved chunk meets both the hybrid
        and rerank score thresholds required to attempt an answer.
        Mirrors the logic previously in answer_service.should_answer.
        """
        if not chunks:
            return False
        top = chunks[0]
        if float(top.get("hybrid_score", 0.0)) < MIN_HYBRID_SCORE_TO_ANSWER:
            return False
        if float(top.get("rerank_score", 0.0)) < MIN_RERANK_SCORE_TO_ANSWER:
            return False
        return True

    @staticmethod
    def _map_sources(chunks: List[Dict]) -> List[Dict]:
        """
        Map retrieved chunks to the citation format expected by
        answer_service and the Streamlit UI.
        """
        return [
            {
                "doc_name":      chunk.get("doc_name", "unknown"),
                "chunk_id":      chunk.get("chunk_id", -1),
                "section_title": chunk.get("section_title", "General"),
                "text":          chunk.get("text", ""),
                "hybrid_score":  chunk.get("hybrid_score"),
                "rerank_score":  chunk.get("rerank_score"),
            }
            for chunk in chunks
        ]

    @staticmethod
    def _build_context_string(
        chunks: List[Dict],
        max_chunks: int = MAX_CONTEXT_CHUNKS,
    ) -> str:
        """
        Format retrieved chunks into the context block injected into the
        LLM prompt. Includes provenance metadata (doc, section, scores)
        so the model can cite sources accurately.
        """
        selected = chunks[:max_chunks]
        parts = []
        for chunk in selected:
            parts.append(
                f"Source: {chunk.get('doc_name', 'unknown')} | "
                f"Section: {chunk.get('section_title', 'General')} | "
                f"Section ID: {chunk.get('section_id', 0)} | "
                f"Chunk ID: {chunk.get('chunk_id', -1)} | "
                f"Semantic Score: {float(chunk.get('semantic_score', 0.0)):.4f} | "
                f"Keyword Score: {float(chunk.get('keyword_score', 0.0)):.4f} | "
                f"Hybrid Score: {float(chunk.get('hybrid_score', 0.0)):.4f} | "
                f"Rerank Score: {float(chunk.get('rerank_score', 0.0)):.4f}\n"
                f"{chunk.get('text', '')}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _empty_result() -> Dict:
        return {
            "chunks":            [],
            "sources":           [],
            "context_string":    "",
            "sufficient":        False,
            "retrieval_quality": "empty",
            "top_hybrid_score":  0.0,
            "top_rerank_score":  0.0,
        }
