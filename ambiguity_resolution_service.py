from __future__ import annotations

from typing import Dict
from uuid import uuid4


def create_pending_intent_id() -> str:
    return str(uuid4())


def build_ambiguity_question(user_input: str, subtype: str | None, ambiguity_reason: str | None) -> str:
    subtype = subtype or "generic_business_request"

    if ambiguity_reason == "question_requirement_conflict":
        return (
            "This could go in two directions. Are you trying to understand the topic first, "
            "or do you want me to help define a new requirement for it?"
        )

    if ambiguity_reason == "exploratory_requirement_mix":
        return (
            "This sounds exploratory. Are you trying to understand the current state, "
            "or define something new to build?"
        )

    if subtype in {"workflow_automation", "integration_request", "data_pipeline"}:
        return (
            "Before I route this, are you trying to understand the current process or integration, "
            "or do you want to define a new implementation requirement?"
        )

    if subtype in {"data_view", "structured_extract", "reporting_output", "interactive_dashboard"}:
        return (
            "Before I move forward, are you looking for an explanation or recommendation first, "
            "or do you want to define a new output requirement?"
        )

    return (
        "Before I route this, are you asking a question to understand the topic, "
        "or do you want to define a new requirement?"
    )


def build_ambiguity_response(user_input: str, subtype: str | None, ambiguity_reason: str | None, session_id: str) -> Dict:
    question = build_ambiguity_question(user_input, subtype, ambiguity_reason)
    return {
        "mode": "AMBIGUOUS",
        "status": "CLARIFICATION_REQUIRED",
        "message": question,
        "session_id": session_id,
        "question_result": None,
        "ba_result": {
            "stage": "clarification",
            "requirement_state": {
                "original_request": user_input,
                "conversation_history": [{"role": "user", "content": user_input}],
            },
            "interpreted_summary": {
                "summary_text": "",
            },
            "current_question": question,
            "current_question_reason": "The system needs one routing clarification before choosing the right path.",
        },
    }


def resolve_ambiguous_followup(original_request: str, followup: str) -> str:
    text = (followup or "").strip().lower()

    question_signals = {
        "understand",
        "explain",
        "question",
        "current state",
        "current process",
        "recommendation",
        "advice",
        "learn",
    }
    requirement_signals = {
        "build",
        "define",
        "requirement",
        "implement",
        "create",
        "new implementation",
        "move forward",
        "yes build",
    }

    if any(signal in text for signal in question_signals):
        return "QUESTION"

    if any(signal in text for signal in requirement_signals):
        return "REQUIREMENT"

    if text in {"question", "understand", "explain"}:
        return "QUESTION"

    if text in {"requirement", "build", "define", "implement"}:
        return "REQUIREMENT"

    # default bias: if the user explicitly answers unclearly, keep it in question mode first
    return "QUESTION"
