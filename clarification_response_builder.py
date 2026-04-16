from __future__ import annotations

import json
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from src.config import ROOT_DIR, CLAUDE_MODEL_NAME

load_dotenv(dotenv_path=ROOT_DIR / ".env")

from anthropic import Anthropic

# Generic messages from ba_service that carry no shape or metadata content.
# When message equals one of these, we do NOT prepend it — the reflection
# text alone is sufficient.
_GENERIC_OPENING_MESSAGES = {
    "I've started shaping this request into a structured requirement package.",
    "I incorporated your last answer and I need one more detail before moving forward.",
}


def _sentence(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return cleaned + "."


def _llm_client() -> Optional[Anthropic]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        return Anthropic(api_key=api_key)
    except Exception:
        return None


def _format_reflection_payload(payload: Dict) -> Optional[str]:
    fmt = str(payload.get("format", "sentence")).strip().lower()
    reflection = str(payload.get("reflection", "")).strip()
    bullets = payload.get("bullets") or []

    if fmt == "bullets" and isinstance(bullets, list):
        clean_bullets = [str(item).strip() for item in bullets if str(item).strip()]
        if not clean_bullets:
            return reflection or None

        bullet_text = "\n".join([f"- {item}" for item in clean_bullets])

        if reflection:
            return f"{reflection}\n{bullet_text}"

        return bullet_text

    return reflection or None


def _generate_reflection_with_llm(
    user_input: str,
    interpreted: Dict,
) -> Optional[str]:
    client = _llm_client()
    if not client:
        return None

    try:
        context_summary = interpreted.get("fields_to_update", {}) or {}

        prompt = f"""
You are helping structure a business request into clear, executable requirements.

Return ONLY valid JSON.

Schema:
{{
  "format": "sentence" or "bullets",
  "reflection": string,
  "bullets": optional list of strings
}}

Rules:
- Write 1 or 2 sentences maximum
- Use "sentence" for a simple reflection
- Use "bullets" only when the user input naturally contains multiple grouped items
- Make the reflection feel conversational and forward-moving
- The reflection should do one useful job:
  - confirm direction
  - validate an input or dependency
  - show progress in shaping the request
  - connect the answer to business value
- Do not just restate the user input
- Do not sound like documentation
- Do not ask a question
- Do not mention system steps or missing fields
- Do not claim you will build or deliver the solution
- Avoid repetitive openers like:
  - "You're looking to"
  - "This will help"
  - "Got it"
  - "Understood"

User input:
{user_input}

Interpreted context:
{context_summary}

Output:
"""
        response = client.messages.create(
            model=CLAUDE_MODEL_NAME,
            max_tokens=180,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        for block in response.content:
            text += getattr(block, "text", "") or ""

        payload = json.loads(text.strip())
        return _format_reflection_payload(payload)

    except Exception:
        return None


def _fallback_reflection(user_input: str) -> str:
    base = user_input.strip()
    if base.lower().startswith("we need"):
        base = base[7:].strip()
    return f"This looks like a request to define {base}."


def build_clarification_feedback(
    user_input: str,
    interpreted: Dict,
    next_field: Optional[str],
    next_question: Optional[str],
    current_question: Optional[str] = None,
    current_question_reason: Optional[str] = None,
    opening_message: Optional[str] = None,
) -> Dict:
    """
    Build the clarification feedback payload for a single BA turn.

    opening_message — optional message from ba_service containing the
    shape-aware opening and any metadata note. When provided and non-generic,
    it replaces the hardcoded "Happy to help with that." prefix so the user
    sees the Meaning Agent's resolved label and any metadata overlap warning
    on the very first turn.
    """
    fields_to_update = interpreted.get("fields_to_update", {}) or {}
    answer_status = "sufficient" if interpreted.get("should_override_single_field_write") else "partial"

    if not fields_to_update and next_field:
        answer_status = "weak"

    reflection = _generate_reflection_with_llm(user_input, interpreted)
    if not reflection:
        reflection = _fallback_reflection(user_input)

    final_question = _sentence(next_question or "")

    if answer_status == "weak":
        # Determine the opener for the first-turn response.
        # If ba_service provided a shape-aware or metadata-enriched message,
        # use it instead of the generic "Happy to help with that." hardcode.
        # This is the fix: the generic message was swallowing the shape label
        # and metadata note that ba_service constructed.
        clean_opening = (opening_message or "").strip()
        if clean_opening and clean_opening not in _GENERIC_OPENING_MESSAGES:
            opener = clean_opening
        else:
            opener = "Happy to help with that."

        reflection_text = (
            f"{opener}\n\n"
            f"{reflection}\n\n"
            f"I'll shape this into a clear requirement before execution."
        )
    else:
        reflection_text = reflection

    return {
        "answer_status": answer_status,
        "reflection_text": reflection_text,
        "next_question": f"\n\n**{final_question}**",
        "current_question": current_question,
        "current_question_reason": current_question_reason,
        "next_field": next_field,
    }
