from __future__ import annotations

from typing import Dict


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def is_basic_definition_question(text: str) -> bool:
    normalized = _normalize(text)
    return (
        normalized.startswith("what is ")
        or normalized.startswith("what are ")
        or normalized.startswith("define ")
    )


def _extract_term(question: str) -> str:
    normalized = _normalize(question)
    for prefix in ("what is ", "what are ", "define "):
        if normalized.startswith(prefix):
            return normalized[len(prefix):].rstrip(" ?.")
    return normalized.rstrip(" ?.")


def answer_basic_definition(question: str) -> Dict:
    term = _extract_term(question)
    answer = (
        f"{term.capitalize()} generally refers to a concept, process, or asset used for a specific purpose. "
        "I can define it more precisely in a business, data, or technical context."
    )

    return {
        "answer": answer,
        "answered": True,
        "confidence": "medium",
        "grounding": {
            "score": None,
            "verdict": "emergency_definition_fallback",
        },
        "sources": [],
        "used_fallback": True,
        "term": term,
        "mode": "CONCEPT",
        "needs_clarification": True,
    }


def build_partial_answer_with_guidance(question: str) -> Dict:
    normalized = _normalize(question)

    if "workflow" in normalized:
        answer = (
            "At a high level, a workflow is the sequence of steps used to move work from request to outcome. "
            "In business and data settings, that usually means people, decisions, systems, and handoffs working together."
        )
        next_step = "Are you asking about workflows conceptually, or how a workflow should be designed in this system?"
    elif "integration" in normalized:
        answer = (
            "At a high level, an integration is a connection between systems so data, events, or actions can move reliably between them. "
            "That often involves a source, a target, mapping rules, and failure handling."
        )
        next_step = "Are you asking in general, or about designing a specific integration?"
    elif "dashboard" in normalized:
        answer = (
            "At a high level, a dashboard is a decision-support surface that summarizes the metrics, trends, or breakdowns a user needs to monitor and act on."
        )
        next_step = "Are you asking conceptually, or defining a new dashboard requirement?"
    else:
        answer = (
            "I can give a best-effort answer based on the question as written, but I would need a bit more context to make it more precise."
        )
        next_step = "Do you want a conceptual explanation, or are you trying to define something specific to build?"

    return {
        "answer": answer + "\n\n" + next_step,
        "answered": True,
        "confidence": "medium",
        "grounding": {
            "score": None,
            "verdict": "conceptual_fallback",
        },
        "sources": [],
        "used_fallback": True,
        "term": None,
        "mode": "CONCEPT",
        "needs_clarification": True,
    }