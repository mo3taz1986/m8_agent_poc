from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from src.config import ROOT_DIR, CLAUDE_MODEL_NAME

load_dotenv(dotenv_path=ROOT_DIR / ".env")


def _client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except Exception:
        return None


def _truncate(text: str, max_chars: int = 6000) -> str:
    """Truncate to avoid exceeding token limits on large documents."""
    return text[:max_chars] if len(text) > max_chars else text


def generate_context_summary(file_name: str, extracted_text: str) -> Dict:
    """
    Generate a structured Context Highlights summary from ingested text.

    Returns a dict with:
        name        — original filename
        summary     — 2–4 sentence high-level description
        topics      — 3–5 key themes detected
        business_area — e.g. Finance, Customer Analytics, Risk
        signals     — KPIs, systems, processes, policies detected
        potential_use — how this context may help the requirement
        raw_text_preview — first 300 chars for UI display
    """
    client = _client()
    if not client:
        return _fallback_summary(file_name, extracted_text)

    try:
        truncated = _truncate(extracted_text)

        prompt = f"""
You are analysing a business document uploaded as context for a requirement shaping session.

Return ONLY valid JSON matching this schema exactly:
{{
  "summary": "2 to 4 sentence high-level description of what this document covers",
  "topics": ["topic 1", "topic 2", "topic 3"],
  "business_area": "single business area e.g. Finance Analytics, Customer Risk, Data Governance",
  "signals": ["signal 1", "signal 2", "signal 3"],
  "potential_use": "one sentence on how this context may help shape a delivery requirement"
}}

Rules:
- summary: 2–4 sentences, plain language, no jargon
- topics: 3–5 items, short noun phrases only
- business_area: single value, be specific
- signals: 3–6 items — look for KPIs, systems, data sources, processes, policies, metrics
- potential_use: one sentence, practical and grounded
- Return ONLY the JSON object, no preamble, no markdown

Document name: {file_name}

Document content:
{truncated}
"""

        response = client.messages.create(
            model=CLAUDE_MODEL_NAME,
            max_tokens=500,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        for block in response.content:
            text += getattr(block, "text", "") or ""

        parsed = json.loads(text.strip())

        return {
            "name":             file_name,
            "summary":         str(parsed.get("summary", "")).strip(),
            "topics":          _clean_list(parsed.get("topics", [])),
            "business_area":   str(parsed.get("business_area", "")).strip(),
            "signals":         _clean_list(parsed.get("signals", [])),
            "potential_use":   str(parsed.get("potential_use", "")).strip(),
            "raw_text_preview": extracted_text[:300].strip(),
        }

    except Exception:
        return _fallback_summary(file_name, extracted_text)


def _clean_list(items) -> List[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _fallback_summary(file_name: str, extracted_text: str) -> Dict:
    """
    Used when the LLM call fails or no API key is set.
    Returns a minimal but valid summary so the upload flow is not blocked.
    """
    preview = extracted_text[:300].strip()
    word_count = len(extracted_text.split())

    return {
        "name":             file_name,
        "summary":         f"Document uploaded: {file_name}. Contains approximately {word_count} words.",
        "topics":          ["Business context", "Uploaded document"],
        "business_area":   "Unknown",
        "signals":         [],
        "potential_use":   "Context available to ground requirement shaping.",
        "raw_text_preview": preview,
    }
