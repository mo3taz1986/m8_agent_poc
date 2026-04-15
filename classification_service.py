from __future__ import annotations
 
from typing import Dict
 
from src.services.classification_fallback_service import fallback_classify_requirement_subtype
 
SUBTYPE_SYNONYMS = {
    "interactive_dashboard": [
        "dashboard",
        "scorecard",
        "kpi dashboard",
        "metrics dashboard",
    ],
    "reporting_output": [
        "report",
        "reporting",
        "statement",
        "summary report",
    ],
    "structured_extract": [
        "table",
        "extract",
        "dataset",
        "csv",
        "file extract",
        "data extract",
    ],
    "data_view": [
        "database view",
        "sql view",
        "materialized view",
        "view",
    ],
    "data_pipeline": [
        "pipeline",
        "etl",
        "elt",
        "data pipeline",
    ],
    "integration_request": [
        "integration",
        "feed",
        "sync",
        "api",
        "api feed",
        "interface",
        "connection",
        "connect",
    ],
    "workflow_automation": [
        "workflow",
        "process",
        "approval flow",
        "automation",
        "intake approval",
    ],
    "analytical_model": [
        "model",
        "prediction",
        "forecast",
        "scoring model",
    ],
}
 
QUESTION_STARTERS = (
    "what",
    "how",
    "why",
    "when",
    "where",
    "who",
    "which",
    "is",
    "are",
    "do",
    "does",
    "did",
)
 
EXPLICIT_REQUIREMENT_STARTERS = (
    "i request",
    "we request",
    "i need",
    "we need",
    "i want",
    "we want",
    "looking for",
    "please create",
    "please build",
    "please generate",
    "can you create",
    "can you build",
    "help me create",
    "help me build",
)
 
TASK_KEYWORDS = {
    "create jira",
    "open jira",
    "make ticket",
    "create ticket",
    "assign this",
    "send this",
    "execute this",
    "do this now",
    "submit this",
}
 
REQUIREMENT_KEYWORDS = {
    # Original delivery artifact keywords
    "build",
    "create",
    "develop",
    "design",
    "implement",
    "dashboard",
    "pipeline",
    "workflow",
    "solution",
    "report",
    "model",
    "system",
    "view",
    "extract",
    "dataset",
    "feed",
    "integration",
    "approval",
    "database",
    "table",
    # Business capability keywords — these appear in stakeholder-driven
    # requirement statements that don't use imperative verbs.
    # e.g. "leadership needs profitability visibility by product"
    "visibility",
    "profitability",
    "tracking",
    "monitoring",
    "insight",
    "insights",
    "performance",
    "metrics",
    "kpi",
    "kpis",
    "reporting",
    "scorecard",
    "breakdown",
    "analysis",
    "analytics",
    "forecast",
    "forecasting",
    "trend",
    "trends",
    "attribution",
    "churn",
    "retention",
    "conversion",
    "revenue",
    "margin",
    "cost",
    "spend",
}
 
SUBTYPE_TO_TYPE = {
    "interactive_dashboard": "interactive_dashboard",
    "reporting_output": "reporting_output",
    "structured_extract": "structured_extract",
    "data_view": "data_view",
    "data_pipeline": "data_pipeline",
    "integration_request": "integration_request",
    "workflow_automation": "workflow_automation",
    "analytical_model": "analytical_model",
    "generic_business_request": "generic_business_request",
}
 
VAGUE_REQUIREMENT_PATTERNS = (
    # Original patterns
    "visibility into",
    "visibility for",
    "insight into",
    "understanding of",
    "something for",
    "a way to",
    "expose data",
    "downstream tools",
    "use consistently",
    "reusable structure",
    "downstream consumption",
    # Stakeholder-need patterns — third-person expressions of capability need.
    # These ensure that statements like "leadership needs visibility by product"
    # are recognised as requirement signals even without imperative verbs.
    "needs visibility",
    "need visibility",
    "needs insight",
    "need insight",
    "needs reporting",
    "need reporting",
    "needs tracking",
    "need tracking",
    "needs monitoring",
    "need monitoring",
    "needs a dashboard",
    "need a dashboard",
    "needs a report",
    "need a report",
    "needs access to",
    "need access to",
    "needs better",
    "need better",
    "requires visibility",
    "require visibility",
    "requires reporting",
    "require reporting",
    "visibility by",
    "breakdown by",
    "tracking by",
    "performance by",
    "metrics by",
    "reporting by",
)
 
ABSTRACT_ARCHITECTURE_PATTERNS = (
    "expose data",
    "downstream tools",
    "use consistently",
    "reusable structure",
    "downstream consumption",
    "consumed consistently",
    "query consistently",
    "usable downstream",
)
 
 
def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().strip().split())
 
 
def normalize_requirement_phrase(text: str) -> str:
    normalized = normalize_text(text)
 
    prefixes = (
        "i request ",
        "we request ",
        "i need ",
        "we need ",
        "i want ",
        "we want ",
        "looking for ",
        "please create ",
        "please build ",
        "please generate ",
        "can you create ",
        "can you build ",
        "help me create ",
        "help me build ",
    )
    for prefix in prefixes:
        if normalized.startswith(prefix):
            return normalized[len(prefix):].strip()
    return normalized
 
 
def rule_classify_requirement_subtype(original_request: str) -> Dict:
    text = normalize_requirement_phrase(original_request)
 
    best_subtype = "generic_business_request"
    best_phrase = None
 
    for subtype, phrases in SUBTYPE_SYNONYMS.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            if phrase in text:
                best_subtype = subtype
                best_phrase = phrase
                break
        if best_phrase:
            break
 
    if best_subtype != "generic_business_request":
        confidence = 0.92 if best_phrase and len(best_phrase.split()) > 1 else 0.82
        return {
            "subtype": best_subtype,
            "confidence": confidence,
            "method": "rules",
            "matched_phrase": best_phrase,
            "normalized_text": text,
        }
 
    tokens = set(text.replace(",", " ").replace(".", " ").split())
    keyword_overlap = tokens.intersection(REQUIREMENT_KEYWORDS)
    if keyword_overlap:
        return {
            "subtype": "generic_business_request",
            "confidence": 0.55,
            "method": "rules",
            "matched_phrase": ", ".join(sorted(keyword_overlap)[:3]),
            "normalized_text": text,
        }
 
    return {
        "subtype": "generic_business_request",
        "confidence": 0.35,
        "method": "rules",
        "matched_phrase": None,
        "normalized_text": text,
    }
 
 
def classify_requirement_subtype(original_request: str) -> str:
    result = classify_requirement_subtype_with_confidence(original_request)
    return result["subtype"]
 
 
def classify_requirement_subtype_with_confidence(original_request: str) -> Dict:
    rule_result = rule_classify_requirement_subtype(original_request)
 
    if rule_result["confidence"] >= 0.75:
        return rule_result
 
    fallback_result = fallback_classify_requirement_subtype(
        original_request=original_request,
        normalized_text=rule_result["normalized_text"],
    )
 
    if fallback_result and fallback_result.get("confidence", 0.0) > rule_result["confidence"]:
        return fallback_result
 
    return rule_result
 
 
def classify_requirement_subtype_strong(original_request: str) -> Dict:
    """
    Stronger second-pass classification for cases where requirement intent
    has already been confirmed after ambiguity resolution.
    """
    rule_result = rule_classify_requirement_subtype(original_request)
    fallback_result = fallback_classify_requirement_subtype(
        original_request=original_request,
        normalized_text=rule_result["normalized_text"],
    )
 
    if fallback_result and fallback_result.get("confidence", 0.0) >= rule_result["confidence"]:
        return fallback_result
 
    return rule_result
 
 
def infer_request_type(original_request: str) -> str:
    subtype = classify_requirement_subtype(original_request)
    return SUBTYPE_TO_TYPE.get(subtype, "generic_business_request")
 
 
def _has_vague_requirement_language(text: str) -> bool:
    return any(pattern in text for pattern in VAGUE_REQUIREMENT_PATTERNS)
 
 
def _has_abstract_architecture_language(text: str) -> bool:
    return any(pattern in text for pattern in ABSTRACT_ARCHITECTURE_PATTERNS)
 
 
def classify_intent(user_input: str) -> Dict:
    text = normalize_text(user_input)
    normalized_requirement = normalize_requirement_phrase(user_input)
 
    if not text:
        return {
            "intent": "QUESTION",
            "confidence": 1.0,
            "subtype": None,
            "subtype_confidence": 0.0,
            "method": "rules",
            "ambiguity_reason": None,
        }
 
    for phrase in TASK_KEYWORDS:
        if phrase in text:
            return {
                "intent": "TASK",
                "confidence": 0.98,
                "subtype": None,
                "subtype_confidence": 0.0,
                "method": "rules",
                "ambiguity_reason": None,
            }
 
    subtype_result = classify_requirement_subtype_with_confidence(normalized_requirement)
    subtype = subtype_result["subtype"]
    subtype_confidence = subtype_result["confidence"]
 
    question_signal = text.endswith("?") or text.startswith(QUESTION_STARTERS)
    explicit_requirement_signal = text.startswith(EXPLICIT_REQUIREMENT_STARTERS)
    tokens = set(normalized_requirement.replace(",", " ").replace(".", " ").split())
    keyword_requirement_signal = bool(tokens.intersection(REQUIREMENT_KEYWORDS))
    vague_requirement_signal = _has_vague_requirement_language(normalized_requirement)
    abstract_architecture_signal = _has_abstract_architecture_language(normalized_requirement)
 
    exploratory_signal = (
        text.startswith("should we")
        or text.startswith("trying to understand")
        or text.startswith("looking into")
        or text.startswith("considering")
        or text.startswith("thinking about")
    )
 
    if explicit_requirement_signal and (vague_requirement_signal or abstract_architecture_signal):
        return {
            "intent": "AMBIGUOUS",
            "confidence": 0.58,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": subtype_result.get("method", "rules"),
            "ambiguity_reason": "vague_requirement_starter",
        }
 
    if explicit_requirement_signal:
        return {
            "intent": "REQUIREMENT",
            "confidence": 0.97,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": "rules+explicit_starter",
            "ambiguity_reason": None,
        }
 
    if question_signal and subtype_confidence < 0.75:
        return {
            "intent": "QUESTION",
            "confidence": 0.90,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": "rules",
            "ambiguity_reason": None,
        }
 
    ambiguous_conflict = False
    ambiguity_reason = None
 
    if exploratory_signal and (subtype_confidence >= 0.60 or keyword_requirement_signal):
        ambiguous_conflict = True
        ambiguity_reason = "exploratory_requirement_mix"
    elif question_signal and subtype_confidence >= 0.75:
        ambiguous_conflict = True
        ambiguity_reason = "question_requirement_conflict"
    elif subtype == "generic_business_request" and 0.45 <= subtype_confidence <= 0.70 and keyword_requirement_signal:
        ambiguous_conflict = True
        ambiguity_reason = "low_confidence_requirement"
    elif abstract_architecture_signal and subtype == "generic_business_request":
        ambiguous_conflict = True
        ambiguity_reason = "abstract_architecture_intent"
 
    if ambiguous_conflict:
        return {
            "intent": "AMBIGUOUS",
            "confidence": 0.55,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": subtype_result.get("method", "rules"),
            "ambiguity_reason": ambiguity_reason,
        }
 
    if subtype != "generic_business_request" and subtype_confidence >= 0.6:
        return {
            "intent": "REQUIREMENT",
            "confidence": 0.85,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": subtype_result.get("method", "rules"),
            "ambiguity_reason": None,
        }
 
    if text.startswith(QUESTION_STARTERS):
        return {
            "intent": "QUESTION",
            "confidence": 0.84,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": "rules",
            "ambiguity_reason": None,
        }
 
    if keyword_requirement_signal:
        return {
            "intent": "REQUIREMENT",
            "confidence": 0.72,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": "rules+keywords",
            "ambiguity_reason": None,
        }
 
    # Tightened default fallback.
    # Previously this always returned QUESTION at 0.60, which caused statements
    # of need with no question markers to be silently misrouted.
    # Now: if there's no question signal at all but there is some subtype
    # confidence above 0.40, treat as AMBIGUOUS so the user gets a
    # clarification prompt rather than a wrong answer.
    if not question_signal and subtype_confidence >= 0.40:
        return {
            "intent": "AMBIGUOUS",
            "confidence": 0.52,
            "subtype": subtype,
            "subtype_confidence": subtype_confidence,
            "method": "rules+fallback_ambiguity",
            "ambiguity_reason": "low_confidence_requirement",
        }
 
    return {
        "intent": "QUESTION",
        "confidence": 0.60,
        "subtype": subtype,
        "subtype_confidence": subtype_confidence,
        "method": "rules",
        "ambiguity_reason": None,
    }
