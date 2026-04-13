from __future__ import annotations

from typing import Dict, Set


ARTIFACT_TERMS: Set[str] = {
    "dashboard",
    "report",
    "view",
    "dataset",
    "extract",
    "workflow",
    "pipeline",
    "integration",
    "model",
    "table",
    "api",
    "feed",
    "scorecard",
    "mart",
}

NOVELTY_TERMS: Set[str] = {
    "new capability",
    "new concept",
    "not defined",
    "never done",
    "nobody has defined",
    "unique concept",
    "from scratch",
    "brand new",
}


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _contains_any(text: str, terms: Set[str]) -> bool:
    return any(term in text for term in terms)


def should_trigger_intent_deepening(user_input: str, intent_result: Dict) -> bool:
    text = _normalize(user_input)
    intent = intent_result.get("intent")
    subtype = intent_result.get("subtype") or "generic_business_request"
    subtype_confidence = float(intent_result.get("subtype_confidence", 0.0) or 0.0)

    if intent != "REQUIREMENT":
        return False

    if _contains_any(text, ARTIFACT_TERMS):
        return False

    if _contains_any(text, NOVELTY_TERMS):
        return True

    if subtype == "generic_business_request":
        return True

    if subtype_confidence < 0.60:
        return True

    return False


def build_intent_deepening_question(user_input: str, intent_result: Dict) -> str:
    return (
        "Before I shape requirements, what should the first version actually provide: "
        "an executive dashboard or report, a reusable dataset or view, "
        "an operational workflow, or something else?"
    )


def build_intent_deepening_response(user_input: str, intent_result: Dict, session_id: str) -> Dict:
    question = build_intent_deepening_question(user_input, intent_result)
    return {
        "mode": "INTENT_DEEPENING",
        "status": "CLARIFICATION_REQUIRED",
        "message": question,
        "session_id": session_id,
        "question_result": None,
        "ba_result": {
            "stage": "intent_deepening",
            "requirement_state": {
                "original_request": user_input,
                "conversation_history": [{"role": "user", "content": user_input}],
            },
            "interpreted_summary": {
                "summary_text": "",
            },
            "current_question": question,
            "current_question_reason": (
                "The system needs one deeper clarification before categorizing the requirement path."
            ),
        },
    }


def merge_deepening_context(original_request: str, deepening_answer: str) -> str:
    answer = (deepening_answer or "").strip()
    if not answer:
        return original_request

    return (
        original_request
        + "\n"
        + "Intent deepening answer: The first version should provide "
        + answer
        + "."
    )