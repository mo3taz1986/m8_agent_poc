from typing import Dict, List

REVISION_KEYWORDS = {
    "business_objective": [
        "objective",
        "goal",
        "purpose",
        "outcome",
        "business case",
        "why",
    ],
    "scope": [
        "scope",
        "in scope",
        "out of scope",
        "too broad",
        "too narrow",
        "drilldown",
        "drill-down",
        "expand",
        "reduce",
    ],
    "stakeholders": [
        "stakeholder",
        "user",
        "audience",
        "consumer",
        "leadership",
        "finance",
        "product",
        "operations",
    ],
    "data_sources": [
        "data",
        "source",
        "system",
        "dataset",
        "table",
        "feed",
        "transaction",
        "customer master",
        "cost",
        "revenue",
    ],
    "frequency": [
        "daily",
        "weekly",
        "monthly",
        "refresh",
        "frequency",
        "cadence",
        "schedule",
    ],
    "success_criteria": [
        "success",
        "measure",
        "metric",
        "kpi",
        "done",
        "validation",
        "criteria",
    ],
}

def extract_impacted_fields(feedback: str) -> List[str]:
    text = feedback.lower().strip()
    impacted = []

    for field, keywords in REVISION_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            impacted.append(field)

    # Fallback if feedback is generic
    if not impacted:
        impacted = ["scope", "business_objective"]

    # Keep order stable and unique
    seen = set()
    ordered = []
    for field in impacted:
        if field not in seen:
            seen.add(field)
            ordered.append(field)

    return ordered

def apply_revision_feedback(requirement_state: Dict, feedback: str) -> Dict:
    impacted_fields = extract_impacted_fields(feedback)

    updated_state = requirement_state.copy()

    for field in impacted_fields:
        updated_state[field] = None

    history = list(updated_state.get("conversation_history", []))
    history.append(
        {
            "role": "user",
            "content": f"REVISION_FEEDBACK: {feedback}",
        }
    )
    updated_state["conversation_history"] = history

    return {
        "updated_state": updated_state,
        "fields_impacted": impacted_fields,
        "regenerate": True,
    }