from __future__ import annotations

import os
from typing import Dict, List, Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from src.config import (
    ROOT_DIR,
    CLAUDE_MODEL_NAME,
    ENABLE_GROUNDING_CHECK,
    MIN_GROUNDING_SCORE_TO_ACCEPT,
)
from src.grounding_check import verify_grounding
from src.agents.context_agent import ContextAgent
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

# Module-level ContextAgent instance — stateless, safe to share.
# answer_service owns the LLM answering layer; ContextAgent owns retrieval.
_context_agent = ContextAgent()


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


def ask_context_llm(question: str, context_string: str) -> str:
    """
    Generate a grounded answer from the pre-built context string.

    Accepts context_string directly (built by ContextAgent) rather than
    raw chunks — answer_service no longer knows about chunk structure.
    """
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
{context_string}

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


def _answer_in_context_mode(
    question: str,
    top_k: int,
    context_agent: Optional[ContextAgent] = None,
) -> Dict:
    """
    Answer a question using retrieved context.

    context_agent — optional pre-instantiated ContextAgent. When provided
    (e.g. passed in from the Leader via graph state) it is used directly.
    Falls back to the module-level instance when not provided, preserving
    full backwards compatibility with existing callers.
    """
    agent = context_agent or _context_agent
    ctx = agent.retrieve(question, top_k=top_k)

    sources = ctx["sources"]

    if not ctx["sufficient"]:
        fallback = build_partial_answer_with_guidance(question)
        fallback["sources"] = sources
        fallback["mode"]    = "CONTEXT"
        fallback["grounding"] = {
            "score":   None,
            "verdict": "refused_pre_retrieval"
                       if ctx["retrieval_quality"] == "empty"
                       else "refused_low_retrieval_quality",
        }
        return fallback

    answer_text = ask_context_llm(question, ctx["context_string"])

    if ENABLE_GROUNDING_CHECK:
        grounding_result = verify_grounding(
            answer=answer_text,
            retrieved_chunks=ctx["chunks"],
            min_grounding_score=MIN_GROUNDING_SCORE_TO_ACCEPT,
        )
    else:
        grounding_result = {
            "grounding_score":   None,
            "grounding_verdict": "disabled",
            "grounded":          True,
        }

    answered = bool(answer_text.strip()) and bool(grounding_result.get("grounded", True))

    if not answered:
        fallback = build_partial_answer_with_guidance(question)
        fallback["sources"] = sources
        fallback["mode"]    = "CONTEXT"
        fallback["grounding"] = {
            "score":   grounding_result.get("grounding_score"),
            "verdict": grounding_result.get("grounding_verdict", "unknown"),
        }
        return fallback

    return {
        "answer":    answer_text,
        "answered":  True,
        "confidence": compute_confidence(True, grounding_result.get("grounding_score")),
        "grounding": {
            "score":   grounding_result.get("grounding_score"),
            "verdict": grounding_result.get("grounding_verdict", "unknown"),
        },
        "sources":            sources,
        "used_fallback":      False,
        "needs_clarification": False,
        "mode":               "CONTEXT",
    }


def ask_question(
    question: str,
    top_k: int = 4,
    mode: Optional[str] = None,
    context_agent: Optional[ContextAgent] = None,
) -> Dict:
    """
    Main public entry point for the Q&A pipeline.

    context_agent — optional ContextAgent instance injected by the Leader.
    When omitted the module-level instance is used (backwards compatible).
    """
    normalized   = (question or "").strip()
    active_mode  = (mode or "").upper()

    if active_mode == "CONCEPT":
        return _answer_in_concept_mode(normalized)

    if active_mode == "CONTEXT":
        return _answer_in_context_mode(normalized, top_k=top_k, context_agent=context_agent)

    if is_basic_definition_question(normalized):
        return _answer_in_concept_mode(normalized)

    return _answer_in_context_mode(normalized, top_k=top_k, context_agent=context_agent)
