from typing import Optional

WEAK_TERMS = {
    "all",
    "everything",
    "anything",
    "not sure",
    "idk",
    "i dont know",
    "i don't know",
    "whatever",
    "na",
    "n/a",
    "none",
    "unknown",
    "tbd",
}


def normalize_answer(answer: Optional[str]) -> str:
    return (answer or "").strip().lower()


def is_weak_answer(answer: Optional[str]) -> bool:
    normalized = normalize_answer(answer)

    if not normalized:
        return True

    if normalized in WEAK_TERMS:
        return True

    if len(normalized) < 5:
        return True

    return False


def build_weak_answer_message(field: Optional[str]) -> str:
    field_messages = {
        "business_objective": "I need a clearer business objective before moving forward. What decision, outcome, or business problem should this support?",
        "scope": "I need a bit more precision on scope before moving forward. What should the first version include, and what should stay out of scope?",
        "stakeholders": "I need a clearer stakeholder definition before moving forward. Who will use this output or make decisions from it?",
        "data_sources": "I need more detail on data inputs before moving forward. Which source systems, datasets, or tables should this rely on?",
        "frequency": "I need a clearer usage cadence before moving forward. How often should this be refreshed, reviewed, or used?",
        "success_criteria": "I need a clearer success measure before moving forward. How will you know this was delivered successfully in business terms?",
    }
    return field_messages.get(
        field,
        "I need a bit more detail before moving forward. Could you clarify this further?",
    )