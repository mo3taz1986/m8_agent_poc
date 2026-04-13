from typing import Dict, Any, List

from src.services.clarification_service import (
    identify_missing_fields,
    generate_single_clarification_question,
    infer_request_type,
    FIELD_REASONING,
    FIELD_LABELS,
)

BASE_FIELD_PRIORITY = {
    "business_objective": 10,
    "scope": 9,
    "success_criteria": 9,
    "data_sources": 8,
    "stakeholders": 7,
    "frequency": 6,
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _value_quality_score(value: Any) -> float:
    if value is None:
        return 0.0

    if not isinstance(value, str):
        return 0.5

    text = value.strip()
    if not text:
        return 0.0

    low_value_tokens = {
        "n/a",
        "na",
        "none",
        "unknown",
        "tbd",
        "not sure",
        "idk",
        "maybe",
        "all",
        "everything",
        "anything",
    }

    if text.lower() in low_value_tokens:
        return 0.1

    if len(text) < 8:
        return 0.3

    if len(text) < 20:
        return 0.6

    return 1.0


def _priority_sequence(requirement_state: Dict) -> List[str]:
    request_type = infer_request_type(requirement_state.get("original_request", ""))

    if request_type == "structured_extract":
        return [
            "scope",
            "data_sources",
            "stakeholders",
            "frequency",
            "business_objective",
            "success_criteria",
        ]

    if request_type == "data_view":
        return [
            "scope",
            "data_sources",
            "stakeholders",
            "frequency",
            "business_objective",
            "success_criteria",
        ]

    if request_type == "interactive_dashboard":
        return [
            "business_objective",
            "scope",
            "stakeholders",
            "data_sources",
            "frequency",
            "success_criteria",
        ]

    if request_type == "reporting_output":
        return [
            "business_objective",
            "scope",
            "stakeholders",
            "data_sources",
            "frequency",
            "success_criteria",
        ]

    if request_type in {"data_pipeline", "integration_request"}:
        return [
            "data_sources",
            "scope",
            "frequency",
            "stakeholders",
            "business_objective",
            "success_criteria",
        ]

    if request_type == "workflow_automation":
        return [
            "business_objective",
            "scope",
            "stakeholders",
            "frequency",
            "data_sources",
            "success_criteria",
        ]

    if request_type == "analytical_model":
        return [
            "business_objective",
            "data_sources",
            "scope",
            "stakeholders",
            "frequency",
            "success_criteria",
        ]

    return [
        "business_objective",
        "scope",
        "stakeholders",
        "data_sources",
        "frequency",
        "success_criteria",
    ]


def _critical_refinement_targets(requirement_state: Dict) -> List[str]:
    ordered_fields = _priority_sequence(requirement_state)
    weak_populated_fields = []

    for field in ordered_fields:
        value = requirement_state.get(field)
        if value is None:
            continue

        score = _value_quality_score(value)
        if score <= 0.3:
            weak_populated_fields.append(field)

    return weak_populated_fields


def _compute_priority(field: str, requirement_state: Dict) -> int:
    ordered_fields = _priority_sequence(requirement_state)
    priority = BASE_FIELD_PRIORITY.get(field, 0)

    if field in ordered_fields:
        priority += max(0, len(ordered_fields) - ordered_fields.index(field))

    request_type = infer_request_type(requirement_state.get("original_request", ""))
    if request_type in {"structured_extract", "data_view"} and field in {"scope", "data_sources"}:
        priority += 3
    if request_type in {"data_pipeline", "integration_request"} and field in {"data_sources", "scope", "frequency"}:
        priority += 3

    return priority


def select_next_field(requirement_state: Dict) -> str | None:
    missing_fields = identify_missing_fields(requirement_state)
    if not missing_fields:
        return None

    ranked = sorted(
        missing_fields,
        key=lambda field: _compute_priority(field, requirement_state),
        reverse=True,
    )
    return ranked[0]


def compute_confidence(requirement_state: Dict) -> float:
    weights = {
        "business_objective": 0.22,
        "scope": 0.18,
        "success_criteria": 0.18,
        "data_sources": 0.18,
        "stakeholders": 0.14,
        "frequency": 0.10,
    }

    base_score = 0.0
    ambiguity_penalty = 0.0

    for field, weight in weights.items():
        value = requirement_state.get(field)
        quality = _value_quality_score(value)
        base_score += quality * weight

        if quality <= 0.3:
            ambiguity_penalty += 0.03
        elif quality <= 0.6:
            ambiguity_penalty += 0.01

    score = max(0.0, min(1.0, base_score - ambiguity_penalty))
    return round(score, 3)


def should_move_to_review(requirement_state: Dict, confidence_score: float) -> bool:
    missing_fields = identify_missing_fields(requirement_state)
    weak_fields = _critical_refinement_targets(requirement_state)

    if missing_fields:
        return False

    if weak_fields:
        return False

    return confidence_score >= 0.75


def _build_reason_for_field(field: str, requirement_state: Dict, refinement: bool = False) -> str:
    request_type = infer_request_type(requirement_state.get("original_request", ""))

    request_type_reasons = {
        ("structured_extract", "scope"): "The extract shape needs to be narrowed before downstream design becomes meaningful.",
        ("structured_extract", "data_sources"): "The extract is not actionable until the source data is clear.",
        ("data_view", "scope"): "The view shape should be defined before downstream consumers rely on it.",
        ("data_view", "data_sources"): "The view cannot be shaped until the source tables and structures are understood.",
        ("interactive_dashboard", "business_objective"): "The dashboard should be anchored to a business decision before defining views.",
        ("data_pipeline", "data_sources"): "The pipeline cannot be shaped until the source and target systems are understood.",
        ("integration_request", "data_sources"): "The integration cannot be designed well until the source and target structures are clear.",
        ("workflow_automation", "business_objective"): "The workflow should be tied to a clear process outcome before broader detail is gathered.",
        ("analytical_model", "business_objective"): "The model should be anchored to a clear prediction or decision outcome first.",
    }

    if refinement:
        return (
            request_type_reasons.get((request_type, field))
            or f"The current answer for {FIELD_LABELS.get(field, field)} is still too weak or ambiguous, so it should be refined before moving on."
        )

    return (
        request_type_reasons.get((request_type, field))
        or FIELD_REASONING.get(
            field,
            "This information is needed to complete the requirement.",
        )
    )


def decide_next_step(requirement_state: Dict) -> Dict:
    confidence_score = compute_confidence(requirement_state)

    if should_move_to_review(requirement_state, confidence_score):
        return {
            "next_action": "REVIEW",
            "confidence_score": confidence_score,
            "missing_fields": [],
            "question_field": None,
            "question_field_label": None,
            "next_question": None,
            "reason": (
                "The requirement appears complete enough to move into review. "
                "Critical fields are populated with acceptable quality and confidence is above threshold."
            ),
        }

    weak_fields = _critical_refinement_targets(requirement_state)
    if weak_fields:
        target_field = weak_fields[0]
        return {
            "next_action": "ASK",
            "confidence_score": confidence_score,
            "missing_fields": identify_missing_fields(requirement_state),
            "question_field": target_field,
            "question_field_label": FIELD_LABELS.get(target_field, target_field),
            "next_question": generate_single_clarification_question(target_field, requirement_state),
            "reason": _build_reason_for_field(target_field, requirement_state, refinement=True),
        }

    next_field = select_next_field(requirement_state)
    next_question = generate_single_clarification_question(next_field, requirement_state) if next_field else None

    return {
        "next_action": "ASK",
        "confidence_score": confidence_score,
        "missing_fields": identify_missing_fields(requirement_state),
        "question_field": next_field,
        "question_field_label": FIELD_LABELS.get(next_field, next_field) if next_field else None,
        "next_question": next_question,
        "reason": _build_reason_for_field(next_field, requirement_state, refinement=False) if next_field else (
            "More clarification is needed before review."
        ),
    }