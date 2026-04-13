from __future__ import annotations

import os
from typing import Dict, List, Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from src.config import (
    ROOT_DIR,
    CLAUDE_MODEL_NAME,
    MAX_CONTEXT_CHUNKS,
    MIN_HYBRID_SCORE_TO_ANSWER,
    MIN_RERANK_SCORE_TO_ANSWER,
    ENABLE_GROUNDING_CHECK,
    MIN_GROUNDING_SCORE_TO_ACCEPT,
)
from src.grounding_check import verify_grounding
from src.hybrid_retriever import retrieve_hybrid_chunks
from src.services.concept_answer_service import answer_concept_question
from src.services.question_fallback_service import (
    answer_basic_definition,
    build_partial_answer_with_guidance,
    is_basic_definition_question,
)

load_dotenv(dotenv_path=ROOT_DIR / ".env")

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found in .env")

client = Anthropic(api_key=api_key)


def compute_confidence(answered: bool, grounding_score: float | None) -> str:
    if not answered:
        return "low"

    if grounding_score is None:
        return "medium"

    if grounding_score >= 0.60:
        return "high"
    if grounding_score >= 0.30:
        return "medium"
    return "low"


def map_sources(retrieved_chunks: List[Dict]) -> List[Dict]:
    sources: List[Dict] = []

    for chunk in retrieved_chunks:
        sources.append(
            {
                "doc_name": chunk.get("doc_name", "unknown"),
                "chunk_id": chunk.get("chunk_id", -1),
                "section_title": chunk.get("section_title", "General"),
                "text": chunk.get("text", ""),
                "hybrid_score": chunk.get("hybrid_score"),
                "rerank_score": chunk.get("rerank_score"),
            }
        )

    return sources


def build_context(retrieved_chunks: List[Dict], max_chunks: int = MAX_CONTEXT_CHUNKS) -> str:
    selected_chunks = retrieved_chunks[:max_chunks]

    context_parts = []
    for chunk in selected_chunks:
        context_parts.append(
            (
                f"Source: {chunk.get('doc_name', 'unknown')} | "
                f"Section: {chunk.get('section_title', 'General')} | "
                f"Section ID: {chunk.get('section_id', 0)} | "
                f"Chunk ID: {chunk.get('chunk_id', -1)} | "
                f"Semantic Score: {float(chunk.get('semantic_score', 0.0)):.4f} | "
                f"Keyword Score: {float(chunk.get('keyword_score', 0.0)):.4f} | "
                f"Hybrid Score: {float(chunk.get('hybrid_score', 0.0)):.4f} | "
                f"Rerank Score: {float(chunk.get('rerank_score', 0.0)):.4f}\\n"
                f"{chunk.get('text', '')}"
            )
        )

    return "\\n\\n".join(context_parts)


def should_answer(retrieved_chunks: List[Dict]) -> bool:
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


def ask_context_llm(question: str, retrieved_chunks: List[Dict]) -> str:
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


def _answer_in_concept_mode(question: str) -> Dict:
    concept_result = answer_concept_question(question)

    if concept_result.get("answered"):
        return concept_result

    return answer_basic_definition(question)


def _answer_in_context_mode(question: str, top_k: int) -> Dict:
    retrieved_chunks = retrieve_hybrid_chunks(question)
    sources = map_sources(retrieved_chunks[:top_k])

    if not should_answer(retrieved_chunks):
        fallback_result = build_partial_answer_with_guidance(question)
        fallback_result["sources"] = sources
        fallback_result["mode"] = "CONTEXT"
        fallback_result["grounding"] = {
            "score": 1.0,
            "verdict": "refused_pre_answer",
        }
        return fallback_result

    answer_text = ask_context_llm(question, retrieved_chunks)

    if ENABLE_GROUNDING_CHECK:
        grounding_result = verify_grounding(
            answer=answer_text,
            retrieved_chunks=retrieved_chunks,
            min_grounding_score=MIN_GROUNDING_SCORE_TO_ACCEPT,
        )
    else:
        grounding_result = {
            "grounding_score": None,
            "grounding_verdict": "disabled",
            "grounded": True,
        }

    answered = bool(answer_text.strip()) and bool(grounding_result.get("grounded", True))

    if not answered:
        fallback_result = build_partial_answer_with_guidance(question)
        fallback_result["sources"] = sources
        fallback_result["mode"] = "CONTEXT"
        fallback_result["grounding"] = {
            "score": grounding_result.get("grounding_score"),
            "verdict": grounding_result.get("grounding_verdict", "unknown"),
        }
        return fallback_result

    return {
        "answer": answer_text,
        "answered": True,
        "confidence": compute_confidence(
            True,
            grounding_result.get("grounding_score"),
        ),
        "grounding": {
            "score": grounding_result.get("grounding_score"),
            "verdict": grounding_result.get("grounding_verdict", "unknown"),
        },
        "sources": sources,
        "used_fallback": False,
        "needs_clarification": False,
        "mode": "CONTEXT",
    }


def ask_question(question: str, top_k: int = 4, mode: Optional[str] = None) -> Dict:
    normalized = (question or "").strip()
    active_mode = (mode or "").upper()

    if active_mode == "CONCEPT":
        return _answer_in_concept_mode(normalized)

    if active_mode == "CONTEXT":
        return _answer_in_context_mode(normalized, top_k=top_k)

    if is_basic_definition_question(normalized):
        return _answer_in_concept_mode(normalized)

    return _answer_in_context_mode(normalized, top_k=top_k)