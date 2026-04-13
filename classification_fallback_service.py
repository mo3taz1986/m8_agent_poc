from __future__ import annotations

import os
from typing import Dict, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None  # type: ignore


_ALLOWED_SUBTYPES = {
    "interactive_dashboard",
    "reporting_output",
    "structured_extract",
    "data_view",
    "data_pipeline",
    "integration_request",
    "workflow_automation",
    "analytical_model",
    "generic_business_request",
}


def _heuristic_fallback(normalized_text: str) -> Dict:
    text = normalized_text.lower()

    if any(term in text for term in ["view", "database view", "sql view", "materialized view"]):
        return {"subtype": "data_view", "confidence": 0.70, "method": "heuristic_fallback"}

    if any(term in text for term in ["extract", "dataset", "csv", "table"]):
        return {"subtype": "structured_extract", "confidence": 0.70, "method": "heuristic_fallback"}

    if any(term in text for term in ["feed", "sync", "api", "interface", "connect"]):
        return {"subtype": "integration_request", "confidence": 0.68, "method": "heuristic_fallback"}

    if any(term in text for term in ["workflow", "approval", "process", "automation"]):
        return {"subtype": "workflow_automation", "confidence": 0.68, "method": "heuristic_fallback"}

    if any(term in text for term in ["pipeline", "etl", "elt"]):
        return {"subtype": "data_pipeline", "confidence": 0.68, "method": "heuristic_fallback"}

    if any(term in text for term in ["dashboard", "scorecard", "kpi"]):
        return {"subtype": "interactive_dashboard", "confidence": 0.68, "method": "heuristic_fallback"}

    if any(term in text for term in ["report", "statement"]):
        return {"subtype": "reporting_output", "confidence": 0.68, "method": "heuristic_fallback"}

    if any(term in text for term in ["model", "forecast", "prediction"]):
        return {"subtype": "analytical_model", "confidence": 0.68, "method": "heuristic_fallback"}

    return {"subtype": "generic_business_request", "confidence": 0.50, "method": "heuristic_fallback"}


def _llm_fallback(original_request: str) -> Optional[Dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or Anthropic is None:
        return None

    try:
        client = Anthropic(api_key=api_key)
        prompt = f"""
Classify the following requirement into exactly one subtype from this list:

interactive_dashboard
reporting_output
structured_extract
data_view
data_pipeline
integration_request
workflow_automation
analytical_model
generic_business_request

Return only the subtype.

Request:
{original_request}
""".strip()

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=20,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        if getattr(response, "content", None):
            block = response.content[0]
            text = (getattr(block, "text", "") or "").strip()

        if text in _ALLOWED_SUBTYPES:
            return {"subtype": text, "confidence": 0.78, "method": "llm_fallback"}

        return None
    except Exception:
        return None


def fallback_classify_requirement_subtype(original_request: str, normalized_text: str) -> Optional[Dict]:
    llm_result = _llm_fallback(original_request)
    if llm_result:
        return llm_result

    return _heuristic_fallback(normalized_text)
