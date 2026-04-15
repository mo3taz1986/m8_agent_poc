from __future__ import annotations
 
import re
from typing import Dict, List, Optional
 
 
SHAPE_KEYWORDS = {
    "dashboard": ["dashboard", "scorecard"],
    "report": ["report", "reporting"],
    "workflow": ["workflow", "approval", "routing"],
    "data_asset": ["dataset", "view", "table"],
    "integration": ["integration", "api", "sync"],
}
 
STAKEHOLDER_HINTS = [
    "leadership",
    "leaders",
    "finance",
    "finance leaders",
    "product",
    "product managers",
    "analytics",
    "analytics teams",
    "executives",
    "operations",
]
 
DIMENSION_HINTS = [
    "segment",
    "customer",
    "product",
    "region",
    "branch",
    "drilldown",
    "drilldowns",
]
 
REQUIRED_FIELDS = [
    "business_objective",
    "scope",
    "stakeholders",
    "data_sources",
    "frequency",
    "success_criteria",
]
 
 
def normalize(text: Optional[str]) -> str:
    return " ".join((text or "").lower().strip().split())
 
 
def extract_shape(text: str) -> Optional[str]:
    text = normalize(text)
 
    for shape, keywords in SHAPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return shape
 
    return None
 
 
def extract_stakeholders(text: str) -> Optional[str]:
    text = normalize(text)
    found = [hint for hint in STAKEHOLDER_HINTS if hint in text]
 
    if not found:
        return None
 
    return ", ".join(sorted(set(hint.title() for hint in found)))
 
 
def extract_dimensions(text: str) -> List[str]:
    text = normalize(text)
    results: List[str] = []
 
    for dim in DIMENSION_HINTS:
        if dim in text:
            title = dim.title()
            if title not in results:
                results.append(title)
 
    return results
 
 
def extract_business_objective(text: str) -> Optional[str]:
    text_lower = text.lower()
 
    patterns = [
        r"(identify .+)",
        r"(track .+)",
        r"(monitor .+)",
        r"(improve .+)",
        r"(enable .+)",
        r"(support .+)",
        r"(take action.+)",
    ]
 
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().rstrip(".")
 
    if "to " in text_lower:
        idx = text_lower.find("to ")
        return text[idx:].strip().rstrip(".")
 
    return None
 
 
def extract_success_criteria(text: str, current_question: Optional[str]) -> Optional[str]:
    normalized_question = normalize(current_question)
    normalized_text = normalize(text)
 
    success_keywords = [
        "successful",
        "success",
        "business result",
        "measurable change",
        "delivering value",
        "valuable",
    ]
 
    if any(keyword in normalized_question for keyword in success_keywords):
        if "take action" in normalized_text:
            return text.strip()
        if any(term in normalized_text for term in ["improve", "increase", "reduce", "adopt", "use"]):
            return text.strip()
 
    return None
 
 
def build_field_updates(
    current_field: Optional[str],
    user_input: str,
    current_question: Optional[str],
    shape: Optional[str],
    stakeholders: Optional[str],
    objective: Optional[str],
    success_criteria: Optional[str],
    dimensions: List[str],
    requirement_state: Optional[Dict] = None,
) -> Dict[str, str]:
    updates: Dict[str, str] = {}
    normalized_question = normalize(current_question)
 
    # Helper: only write to a field if it is not already answered
    # unless it is the field currently being asked about.
    def _can_write(field: str) -> bool:
        if field == current_field:
            return True
        if requirement_state is None:
            return True
        existing = requirement_state.get(field)
        if existing is None:
            return True
        if isinstance(existing, str) and not existing.strip():
            return True
        return False
 
    if shape and _can_write("scope"):
        updates["scope"] = user_input
 
    if stakeholders and _can_write("stakeholders"):
        updates["stakeholders"] = stakeholders
 
    if success_criteria and _can_write("success_criteria"):
        updates["success_criteria"] = success_criteria
    elif objective:
        if any(term in normalized_question for term in ["success", "valuable", "business result", "measurable change"]):
            if _can_write("success_criteria"):
                updates["success_criteria"] = objective
        else:
            if _can_write("business_objective"):
                updates["business_objective"] = objective
 
    if dimensions:
        # Only append dimensions to scope if scope is the current field
        # or scope has not been answered yet, to avoid overwriting a confirmed answer.
        if _can_write("scope"):
            scope_value = updates.get("scope") or user_input
            updates["scope"] = f"{scope_value} | Dimensions: {', '.join(dimensions)}"
 
    if not updates and current_field:
        updates[current_field] = user_input
 
    return updates
 
 
def interpret_clarification_answer(
    original_request: str,
    current_question: Optional[str],
    current_field: Optional[str],
    user_input: str,
    requirement_state: Optional[Dict] = None,
) -> Dict:
    shape = extract_shape(user_input)
    stakeholders = extract_stakeholders(user_input)
    objective = extract_business_objective(user_input)
    dimensions = extract_dimensions(user_input)
    success_criteria = extract_success_criteria(user_input, current_question)
 
    updates = build_field_updates(
        current_field=current_field,
        user_input=user_input,
        current_question=current_question,
        shape=shape,
        stakeholders=stakeholders,
        objective=objective,
        success_criteria=success_criteria,
        dimensions=dimensions,
        requirement_state=requirement_state,
    )
 
    confidence = 0.0
    if shape:
        confidence += 0.25
    if stakeholders:
        confidence += 0.20
    if objective:
        confidence += 0.25
    if success_criteria:
        confidence += 0.20
    if dimensions:
        confidence += 0.10
 
    return {
        "confidence": round(min(confidence, 1.0), 2),
        "shape": shape,
        "stakeholders": stakeholders,
        "business_objective": objective,
        "success_criteria": success_criteria,
        "dimensions": dimensions,
        "fields_to_update": updates,
        "should_override_single_field_write": len(updates) > 1,
    }
