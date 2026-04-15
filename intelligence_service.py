from __future__ import annotations
 
import re
from typing import Dict, List, Optional
 
from src.services.clarification_service import infer_request_type
 
 
REQUEST_TYPE_LABELS = {
    "analytics or reporting capability": "reporting or dashboard use case",
    "data pipeline or data movement capability": "data pipeline or movement use case",
    "workflow or process capability": "workflow or process use case",
    "analytical or modeling capability": "modeling or analytical use case",
    "business capability": "business capability use case",
}
 
 
def _clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text
 
 
def _looks_missing(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    return text in {"", "needs clarification", "unknown", "tbd", "n/a", "na"}
 
 
def _request_label(original_request: str) -> str:
    request_type = infer_request_type(original_request or "")
    return REQUEST_TYPE_LABELS.get(request_type, "business use case")
 
 
def _build_interpretation(original_request: str, requirement_state: Dict) -> str:
    label = _request_label(original_request)
    stakeholders = _clean(requirement_state.get("stakeholders"))
    scope = _clean(requirement_state.get("scope"))
 
    base = f"This looks like a {label}."
 
    if stakeholders and not _looks_missing(stakeholders):
        return f"{base} I'm shaping it for {stakeholders}."
 
    if scope and not _looks_missing(scope):
        return f"{base} I'm using the current scope as the working boundary."
 
    return f"{base} I'm shaping it into a structured requirement."
 
 
def _field_assumption(field: str, value: object) -> Optional[str]:
    text = _clean(value)
    if _looks_missing(text):
        return None
 
    mapping = {
        "business_objective": f"I'm assuming the main outcome is {text}.",
        "scope": f"I'm assuming the effort should stay within this scope: {text}.",
        "stakeholders": f"I'm assuming the primary users or decision-makers are {text}.",
        "data_sources": f"I'm assuming the solution should rely on these data sources or systems: {text}.",
        "frequency": f"I'm assuming the expected cadence is {text}.",
        "success_criteria": f"I'm assuming success will be judged by {text}.",
    }
    return mapping.get(field)
 
 
def _build_assumptions(requirement_state: Dict, current_field: Optional[str]) -> List[str]:
    assumptions: List[str] = []
 
    priority_fields = [
        "business_objective",
        "scope",
        "stakeholders",
        "data_sources",
        "frequency",
        "success_criteria",
    ]
 
    for field in priority_fields:
        if field == current_field:
            continue
        assumption = _field_assumption(field, requirement_state.get(field))
        if assumption:
            assumptions.append(assumption)
        if len(assumptions) >= 2:
            break
 
    if assumptions:
        return assumptions[:2]
 
    fallback_map = {
        "business_objective": "I'm assuming the main business outcome has not been pinned down yet, so that is the first thing to confirm.",
        "scope": "I'm assuming scope boundaries are still open, so I should narrow them before moving forward.",
        "stakeholders": "I'm assuming the target users are still open, so that needs to be confirmed early.",
        "data_sources": "I'm assuming source systems are not confirmed yet, which could affect feasibility.",
        "frequency": "I'm assuming the usage cadence is still open, which may affect design choices.",
        "success_criteria": "I'm assuming success measures are still open, so I should confirm them before review.",
    }
 
    if current_field:
        return [fallback_map.get(current_field, "I'm assuming some critical details are still open and need confirmation.")]
 
    return ["I'm assuming the request is directionally valid and ready for the next workflow step."]
 
 
def _extract_key_terms(text: str) -> List[str]:
    if not text:
        return []
 
    terms: List[str] = []
    for raw in re.split(r"[^a-zA-Z0-9_\-]+", text):
        token = raw.strip()
        if len(token) < 4:
            continue
        low = token.lower()
        if low in {"this", "that", "with", "from", "into", "your", "their", "have", "will", "should", "need", "report", "dashboard"}:
            continue
        if token not in terms:
            terms.append(token)
        if len(terms) >= 4:
            break
    return terms
 
 
def _build_grounding_note(retrieved_context: Optional[List[Dict]]) -> Optional[str]:
    if not retrieved_context:
        return None
 
    best = retrieved_context[0]
    doc_name = _clean(best.get("doc_name")) or "the uploaded context"
    section_title = _clean(best.get("section_title"))
    key_terms = best.get("key_terms") or _extract_key_terms(_clean(best.get("text")))
 
    if key_terms:
        joined = ", ".join(key_terms[:3])
        if section_title and section_title != "General":
            return f"Based on {doc_name}, especially the {section_title} section, I'm aligning to terms like {joined}."
        return f"Based on {doc_name}, I'm aligning to terms like {joined}."
 
    if section_title and section_title != "General":
        return f"Based on {doc_name}, I'm aligning to the {section_title} section."
 
    return f"Based on {doc_name}, I'm aligning to the uploaded context where relevant."
 
 
def _compose_final_response(
    interpretation: str,
    assumptions: List[str],
    grounding_note: Optional[str],
    next_question: str,
    stage: str,
) -> str:
    parts: List[str] = [interpretation]
 
    if grounding_note:
        parts.append(grounding_note)
 
    if assumptions:
        if len(assumptions) == 1:
            parts.append(assumptions[0])
        else:
            parts.append(" ".join(assumptions[:2]))
 
    if next_question:
        if stage == "review_ready":
            parts.append(f"One last confirmation before review: {next_question}")
        else:
            parts.append(next_question)
 
    return "\n\n".join(part.strip() for part in parts if part and part.strip())
 
 
def generate_intelligent_response(
    user_input: str,
    retrieved_context: Optional[List[Dict]] = None,
    ba_state: Optional[Dict] = None,
) -> Dict:
    ba_state = ba_state or {}
    requirement_state = ba_state.get("requirement_state") or {}
    original_request = _clean(requirement_state.get("original_request")) or _clean(user_input)
    stage = _clean(ba_state.get("stage")).lower() or "clarification"
    next_question = _clean(ba_state.get("current_question"))
    current_field = ba_state.get("current_field")
 
    interpretation = _build_interpretation(original_request, requirement_state)
    assumptions = _build_assumptions(requirement_state, current_field)
    grounding_note = _build_grounding_note(retrieved_context)
 
    if not next_question:
        if stage == "review_ready":
            next_question = "Please review the package and decide whether to approve it or request revision."
        elif stage == "execution_ready":
            next_question = "You can now generate the execution package when you're ready."
        elif stage == "jira_payload_ready":
            next_question = "Please review the Jira payload before sending it."
        elif stage == "jira_submitted":
            next_question = "The Jira submission is complete."
        else:
            next_question = "What is the next most important detail to confirm?"
 
    final_response = _compose_final_response(
        interpretation=interpretation,
        assumptions=assumptions,
        grounding_note=grounding_note,
        next_question=next_question,
        stage=stage,
    )
 
    return {
        "interpretation": interpretation,
        "assumptions": assumptions,
        "grounding_note": grounding_note,
        "next_question": next_question,
        "final_response": final_response,
    }
