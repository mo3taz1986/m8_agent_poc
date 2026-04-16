from typing import Dict, List, Optional
 
from src.services.question_strategy_service import (
    generate_strategy_question,
    generate_adaptive_assumptions,
)
from src.services.classification_service import (
    classify_requirement_subtype,
    infer_request_type,
    normalize_requirement_phrase,
)
 
REQUIRED_FIELDS = [
    "business_objective",
    "scope",
    "stakeholders",
    "data_sources",
    "frequency",
    "success_criteria",
]
 
FIELD_LABELS = {
    "business_objective": "Business Objective",
    "scope": "Scope",
    "stakeholders": "Stakeholders",
    "data_sources": "Data Sources",
    "frequency": "Frequency",
    "success_criteria": "Success Criteria",
}
 
FIELD_REASONING = {
    "business_objective": "I need the core objective so I can anchor the request to a clear business outcome.",
    "scope": "I need scope boundaries so the request does not stay too broad or ambiguous.",
    "stakeholders": "I need to know who this is for so the output aligns to the right users and decisions.",
    "data_sources": "I need the data inputs so the request can be grounded in real systems and feasible delivery.",
    "frequency": "I need the expected cadence so the solution aligns with how it will actually be used.",
    "success_criteria": "I need success criteria so the request can be validated against a meaningful outcome.",
}
 
 
def initialize_requirement_state(original_request: str) -> Dict:
    return {
        "original_request": original_request,
        "business_objective": None,
        "scope": None,
        "stakeholders": None,
        "data_sources": None,
        "frequency": None,
        "success_criteria": None,
        "conversation_history": [
            {
                "role": "user",
                "content": original_request,
            }
        ],
    }
 
 
def identify_missing_fields(requirement_state: Dict) -> List[str]:
    missing = []
    for field in REQUIRED_FIELDS:
        value = requirement_state.get(field)
        if value is None:
            missing.append(field)
            continue
        if isinstance(value, str) and not value.strip():
            missing.append(field)
    return missing
 
 
def get_completion_progress(requirement_state: Dict) -> Dict:
    total = len(REQUIRED_FIELDS)
    missing_fields = identify_missing_fields(requirement_state)
    completed = total - len(missing_fields)
    percent_complete = int((completed / total) * 100) if total else 0
 
    return {
        "total_fields": total,
        "completed_fields": completed,
        "missing_fields_count": len(missing_fields),
        "percent_complete": percent_complete,
    }
 
 
def _resolve_request_type(requirement_state: Dict) -> str:
    """
    Resolve the request type for this session.
 
    If the Meaning Agent already locked a category (stored as
    _resolved_request_type on requirement_state by start_requirement_flow),
    use that directly — it is more reliable than re-classifying from the
    raw request string every time.
 
    Falls back to infer_request_type if no pre-resolved type is present.
    """
    pre_resolved = requirement_state.get("_resolved_request_type")
    if pre_resolved:
        return pre_resolved
 
    original_request = (requirement_state.get("original_request") or "").strip()
    return infer_request_type(original_request)
 
 
def build_interpreted_summary(requirement_state: Dict) -> Dict:
    original_request = (requirement_state.get("original_request") or "").strip()
    request_type = _resolve_request_type(requirement_state)
 
    summary_text = (
        f"I understand this as a request for a {request_type.replace('_', ' ')}. "
        f"My goal is to turn it into a structured, execution-ready requirement package."
    )
 
    assumptions = generate_adaptive_assumptions(requirement_state, request_type)
 
    return {
        "request_type": request_type,
        "summary_text": summary_text,
        "assumptions": assumptions,
        "original_request": original_request,
    }
 
 
def get_next_missing_field(requirement_state: Dict) -> Optional[str]:
    missing_fields = identify_missing_fields(requirement_state)
    return missing_fields[0] if missing_fields else None
 
 
def generate_single_clarification_question(field: str, requirement_state: Dict) -> str:
    """
    Generate the next clarifying question for the given field.
 
    Uses _resolve_request_type to honour the Meaning Agent's pre-resolved
    category when available, so question phrasing and priority are aligned
    to the locked delivery shape rather than a re-classification guess.
    """
    request_type = _resolve_request_type(requirement_state)
    return generate_strategy_question(field, requirement_state, request_type)
 
 
def build_reasoning_summary(requirement_state: Dict) -> Dict:
    missing_fields = identify_missing_fields(requirement_state)
    progress = get_completion_progress(requirement_state)
 
    if missing_fields:
        summary_text = (
            f"I understand the direction of the request, but it is still only "
            f"{progress['percent_complete']} percent complete. "
            f"I will ask one focused question at a time to finish shaping it properly."
        )
    else:
        summary_text = (
            "I now have enough information to finalize the requirement package "
            "and prepare delivery-oriented artifacts."
        )
 
    return {
        "summary_text": summary_text,
        "progress": progress,
    }
 
 
def build_single_question_payload(requirement_state: Dict) -> Dict:
    next_field = get_next_missing_field(requirement_state)
 
    if not next_field:
        return {
            "current_field": None,
            "current_field_label": None,
            "current_question": None,
            "current_question_reason": None,
        }
 
    return {
        "current_field": next_field,
        "current_field_label": FIELD_LABELS.get(next_field, next_field),
        "current_question": generate_single_clarification_question(next_field, requirement_state),
        "current_question_reason": FIELD_REASONING.get(
            next_field,
            "This information is needed to complete the requirement."
        ),
    }
