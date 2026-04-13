from typing import Dict, List

from src.services.question_library import (
    QUESTION_LIBRARY,
    DEFAULT_BREAKDOWNS,
    ARTIFACT_BY_SUBTYPE,
)


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _infer_breakdowns(requirement_state: Dict) -> str:
    scope = _clean_text(requirement_state.get("scope")).lower()
    original_request = _clean_text(requirement_state.get("original_request")).lower()
    combined = f"{scope} {original_request}"

    detected = []
    for candidate in ["product", "segment", "region", "customer", "channel", "branch"]:
        if candidate in combined:
            detected.append(candidate)

    if not detected:
        detected = DEFAULT_BREAKDOWNS

    return ", ".join(detected[:3])


def _artifact_label(request_type: str, original_request: str) -> str:
    text = (original_request or "").lower()
    if "dashboard" in text or request_type == "interactive_dashboard":
        return "dashboard"
    if "database view" in text or "sql view" in text or "materialized view" in text or request_type == "data_view":
        return "view"
    if "table" in text or "extract" in text or "dataset" in text or request_type == "structured_extract":
        return "extract"
    if "report" in text or request_type == "reporting_output":
        return "report"
    return ARTIFACT_BY_SUBTYPE.get(request_type, "solution")


def _choose_pattern(patterns: List[str], requirement_state: Dict) -> str:
    history = requirement_state.get("conversation_history", [])
    if not patterns:
        return "What should be captured next to clarify this request?"
    idx = max(0, len(history) - 1) % len(patterns)
    return patterns[idx]


def generate_strategy_question(field: str, requirement_state: Dict, request_type: str) -> str:
    field_patterns = QUESTION_LIBRARY.get(request_type, {}).get(field)
    if not field_patterns:
        field_patterns = QUESTION_LIBRARY["generic_business_request"].get(field, [])

    original_request = _clean_text(requirement_state.get("original_request"))
    artifact = _artifact_label(request_type, original_request)
    breakdowns = _infer_breakdowns(requirement_state)
    pattern = _choose_pattern(field_patterns, requirement_state)

    return pattern.format(
        artifact=artifact,
        breakdowns=breakdowns,
    )


def generate_adaptive_assumptions(requirement_state: Dict, request_type: str) -> List[str]:
    assumptions: List[str] = []
    original_request = _clean_text(requirement_state.get("original_request")).lower()

    if request_type in {"interactive_dashboard", "reporting_output"}:
        if "profit" in original_request or "margin" in original_request:
            assumptions.append("I’m assuming this output is intended to support business review or decision-making rather than raw transaction inspection.")
        else:
            assumptions.append("I’m assuming the first version should focus on decision support rather than trying to answer every possible question.")
    elif request_type == "structured_extract":
        assumptions.append("I’m assuming the first version should prioritize a usable row-level structure before broader downstream enhancements.")
    elif request_type == "data_view":
        assumptions.append("I’m assuming the first version should define a reliable and reusable view shape before expanding into broader modeling concerns.")
    elif request_type in {"data_pipeline", "integration_request"}:
        assumptions.append("I’m assuming the first version should prioritize a clear source-to-target flow before adding broader enrichment or optimization.")
    elif request_type == "workflow_automation":
        assumptions.append("I’m assuming the first version should reduce friction in a defined process rather than redesign the entire operating model.")
    elif request_type == "analytical_model":
        assumptions.append("I’m assuming the first version should focus on a clear analytical outcome before expanding into broader supporting features.")
    else:
        assumptions.append("I’m assuming the first version should stay narrow enough to deliver usable value quickly.")

    stakeholders = _clean_text(requirement_state.get("stakeholders"))
    if not stakeholders:
        assumptions.append("I’m also assuming there is a primary business or technical audience that should shape how this gets defined.")

    return assumptions[:2]