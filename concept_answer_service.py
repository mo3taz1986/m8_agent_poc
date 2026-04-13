from __future__ import annotations

import os
import re
from typing import Dict, Optional

from dotenv import load_dotenv
from src.config import ROOT_DIR, CLAUDE_MODEL_NAME

load_dotenv(dotenv_path=ROOT_DIR / ".env")

from anthropic import Anthropic


DEFAULT_MODEL = CLAUDE_MODEL_NAME
DEFAULT_MAX_TOKENS = int(os.getenv("CONCEPT_ANSWER_MAX_TOKENS", "260"))
DEFAULT_TEMPERATURE = float(os.getenv("CONCEPT_ANSWER_TEMPERATURE", "0.2"))


CONCEPT_SYSTEM_PROMPT = (
    "You answer conceptual user questions clearly, directly, and naturally. "
    "Give the best answer first. "
    "Do not mention internal tooling, retrieval limits, or missing evidence. "
    "If useful, add one sentence that connects the concept to business, data, or systems work. "
    "If the user asked in a specific context such as technical, business, or data, answer in that context. "
    "Only end with one short follow-up question if it genuinely helps."
)


def _normalize(text: str) -> str:
    return " ".join((text or "").strip().split())


def _format_answer(text: str) -> str:
    text = _normalize(text)

    # Put numbered items on separate lines
    text = re.sub(r"\s(\d+\.\s)", r"\n\n\1", text)

    # Add paragraph spacing after sentences when followed by a capital letter
    text = re.sub(r"\.\s+(?=[A-Z])", ".\n\n", text)

    # Pull the final question to the bottom as a clear next step
    last_q = text.rfind("?")
    if last_q != -1:
        before = text[:last_q].strip()
        question_start = max(
            before.rfind("."),
            before.rfind("!"),
            before.rfind("?"),
        )
        if question_start != -1:
            question = text[question_start + 1 : last_q + 1].strip()
            body = before[: question_start + 1].strip()
            if question:
                text = f"{body}\n\n**Next step:**\n{question}"

    return text.strip()


def _llm_answer(question: str) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        client = Anthropic(api_key=api_key)

        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
            system=CONCEPT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Question: {question}"}],
        )

        text = ""
        if getattr(response, "content", None):
            for block in response.content:
                text += getattr(block, "text", "") or ""

        cleaned = _format_answer(text)
        return cleaned if cleaned else None

    except Exception:
        return None


def answer_concept_question(question: str) -> Dict:
    answer = _llm_answer(question)

    if answer:
        return {
            "answer": answer,
            "answered": True,
            "confidence": "high",
            "grounding": {
                "score": None,
                "verdict": "llm_concept_answer",
            },
            "sources": [],
            "used_fallback": False,
            "mode": "CONCEPT",
            "needs_clarification": "?" in answer,
        }

    return {
        "answer": "I can help explain that. Could you clarify what aspect you are interested in?",
        "answered": False,
        "confidence": "low",
        "grounding": {
            "score": None,
            "verdict": "llm_concept_unavailable",
        },
        "sources": [],
        "used_fallback": True,
        "mode": "CONCEPT",
        "needs_clarification": True,
    }