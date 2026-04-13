from typing import Dict, List
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv


load_dotenv()

_client = None
_api_key = os.getenv("ANTHROPIC_API_KEY")
if _api_key:
    _client = Anthropic(api_key=_api_key)


def safe_text(value) -> str:
    if value is None:
        return "Needs clarification"

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else "Needs clarification"

    return str(value)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def truncate_text(text: str, max_len: int = 60) -> str:
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def generate_problem_statement(requirement_state: Dict) -> str:
    original_request = safe_text(requirement_state.get("original_request"))
    business_objective = safe_text(requirement_state.get("business_objective"))
    stakeholders = safe_text(requirement_state.get("stakeholders"))

    return (
        f"The request originated from: '{original_request}'. "
        f"The primary business objective is: {business_objective}. "
        f"The primary stakeholders or intended users are: {stakeholders}."
    )


def generate_assumptions(requirement_state: Dict) -> List[str]:
    assumptions = [
        "The stated business objective reflects the core purpose of the request.",
        "The identified stakeholders are the primary consumers or decision-makers for this capability.",
        "The listed data sources are expected to be available for use unless otherwise constrained.",
    ]

    frequency = safe_text(requirement_state.get("frequency"))
    if frequency != "Needs clarification":
        assumptions.append(
            f"The requested usage or refresh cadence is expected to align with '{frequency}'."
        )

    return assumptions


def generate_constraints(requirement_state: Dict) -> List[str]:
    constraints = [
        "Detailed technical design is not defined in this intake stage.",
        "Delivery sequencing and implementation ownership are not determined in this milestone.",
    ]

    data_sources = safe_text(requirement_state.get("data_sources"))
    if data_sources == "Needs clarification":
        constraints.append("Data source availability remains to be confirmed.")
    else:
        constraints.append(
            f"Solution feasibility depends on access to the following data sources: {data_sources}."
        )

    return constraints


def generate_risks(requirement_state: Dict) -> List[str]:
    risks = []

    if safe_text(requirement_state.get("data_sources")) == "Needs clarification":
        risks.append("Unclear data sources may delay design and delivery.")

    if safe_text(requirement_state.get("success_criteria")) == "Needs clarification":
        risks.append("Undefined success criteria may create ambiguity in delivery outcomes.")

    if safe_text(requirement_state.get("stakeholders")) == "Needs clarification":
        risks.append("Missing stakeholder definition may lead to misaligned expectations.")

    if not risks:
        risks.append(
            "No material intake-stage risks were identified beyond standard delivery uncertainty."
        )

    return risks


def generate_requirement_document(requirement_state: Dict) -> Dict:
    return {
        "problem_statement": generate_problem_statement(requirement_state),
        "business_objective": safe_text(requirement_state.get("business_objective")),
        "scope": safe_text(requirement_state.get("scope")),
        "stakeholders": safe_text(requirement_state.get("stakeholders")),
        "data_requirements": safe_text(requirement_state.get("data_sources")),
        "frequency": safe_text(requirement_state.get("frequency")),
        "success_criteria": safe_text(requirement_state.get("success_criteria")),
        "assumptions": generate_assumptions(requirement_state),
        "constraints": generate_constraints(requirement_state),
        "risks": generate_risks(requirement_state),
        "source_request": safe_text(requirement_state.get("original_request")),
    }


def fallback_epic_meaning(requirement_document: Dict) -> str:
    source = safe_text(requirement_document.get("source_request"))
    objective = safe_text(requirement_document.get("business_objective"))

    base = source if source != "Needs clarification" else objective
    base = clean_text(base)

    fillers = {
        "build",
        "create",
        "develop",
        "need",
        "needs",
        "help",
        "please",
        "should",
        "would",
        "could",
        "ability",
        "capability",
        "allow",
        "leadership",
        "team",
        "users",
        "system",
        "solution",
        "it",
        "this",
        "that",
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "and",
    }

    words = []
    for word in base.split():
        cleaned_word = re.sub(r"[^a-zA-Z0-9\-]", "", word)
        if not cleaned_word:
            continue
        if cleaned_word.lower() in fillers:
            continue
        words.append(cleaned_word)

    compressed = " ".join(words[:5]).strip()
    if not compressed:
        compressed = "Business Capability"

    return truncate_text(compressed, 60)


def generate_ai_epic_name(requirement_document: Dict) -> str:
    source = safe_text(requirement_document.get("source_request"))
    objective = safe_text(requirement_document.get("business_objective"))
    scope = safe_text(requirement_document.get("scope"))
    stakeholders = safe_text(requirement_document.get("stakeholders"))
    success_criteria = safe_text(requirement_document.get("success_criteria"))

    if _client is None:
        return f"AI | Req | {fallback_epic_meaning(requirement_document)}"

    try:
        prompt = f"""
You are generating a Jira Epic title for an enterprise delivery workflow.

Task:
Generate a short, clean Epic name based on the request intent.

Rules:
- Return only the Epic name
- Do not return a sentence
- Do not include verbs like build, create, develop, implement, help
- Prefer noun-style business capability wording
- Max 6 words
- No punctuation except spaces
- Make it sound like a real product or delivery Epic title

Examples:
Customer Profitability Workflow Report
Weekly Revenue Performance Dashboard
Counterparty Data Quality Monitoring
Loan Origination Intake Automation

Input:
Request: {source}
Business objective: {objective}
Scope: {scope}
Stakeholders: {stakeholders}
Success criteria: {success_criteria}
""".strip()

        response = _client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=40,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        title = ""
        if getattr(response, "content", None):
            first_block = response.content[0]
            title = getattr(first_block, "text", "") or ""

        title = clean_text(title).replace('"', "")

        if not title or len(title.split()) > 8:
            raise ValueError("AI title invalid")

        title = truncate_text(title, 60)
        return f"AI | Req | {title}"

    except Exception:
        return f"AI | Req | {fallback_epic_meaning(requirement_document)}"


def generate_epic(requirement_document: Dict) -> Dict:
    objective = safe_text(requirement_document.get("business_objective"))
    scope = safe_text(requirement_document.get("scope"))
    stakeholders = safe_text(requirement_document.get("stakeholders"))
    success_criteria = safe_text(requirement_document.get("success_criteria"))

    title = generate_ai_epic_name(requirement_document)

    return {
        "title": title,
        "description": (
            f"Deliver a capability aligned to the following business objective: {objective}. "
            f"In scope: {scope}. "
            f"Primary stakeholders: {stakeholders}."
        ),
        "business_value": objective,
        "success_metrics": success_criteria,
    }


def apply_story_prefix(title: str, prefix: str) -> str:
    return f"{prefix} | {title}"


def generate_story_acceptance_criteria(
    story_title: str, requirement_document: Dict
) -> List[str]:
    stakeholders = safe_text(requirement_document.get("stakeholders"))
    frequency = safe_text(requirement_document.get("frequency"))
    success_criteria = safe_text(requirement_document.get("success_criteria"))

    return [
        f"The capability described in '{story_title}' is available to the identified stakeholders: {stakeholders}.",
        f"The output aligns to the requested usage or refresh expectation: {frequency}.",
        f"The story contributes measurably to the stated success criteria: {success_criteria}.",
    ]


def generate_user_stories(requirement_document: Dict) -> List[Dict]:
    scope = safe_text(requirement_document.get("scope"))
    stakeholders = safe_text(requirement_document.get("stakeholders"))
    data_requirements = safe_text(requirement_document.get("data_requirements"))
    success_criteria = safe_text(requirement_document.get("success_criteria"))

    stories = [
        {
            "title": apply_story_prefix(
                "Define and validate business-facing output",
                "Analysis",
            ),
            "description": (
                f"As a delivery team, we need to define and validate the expected business-facing output "
                f"so that stakeholders ({stakeholders}) can use it effectively within the intended scope: {scope}."
            ),
            "acceptance_criteria": [],
            "dependencies": ["Stakeholder alignment"],
            "risks": ["Business expectations may remain ambiguous if requirements drift."],
        },
        {
            "title": apply_story_prefix(
                "Integrate required data inputs",
                "Dev",
            ),
            "description": (
                f"As a delivery team, we need to integrate the required data inputs "
                f"so that the solution is grounded in the expected sources: {data_requirements}."
            ),
            "acceptance_criteria": [],
            "dependencies": ["Data access and source availability"],
            "risks": ["Source data readiness may delay delivery."],
        },
        {
            "title": apply_story_prefix(
                "Validate delivery against success criteria",
                "UAT",
            ),
            "description": (
                f"As a delivery team, we need to validate the delivered capability "
                f"so that it meets the stated success criteria: {success_criteria}."
            ),
            "acceptance_criteria": [],
            "dependencies": ["Completion of core capability"],
            "risks": ["Success may be difficult to measure if metrics remain loosely defined."],
        },
    ]

    for story in stories:
        story["acceptance_criteria"] = generate_story_acceptance_criteria(
            story_title=story["title"],
            requirement_document=requirement_document,
        )

    return stories


def generate_epic_and_stories(requirement_document: Dict) -> Dict:
    epic = generate_epic(requirement_document)
    stories = generate_user_stories(requirement_document)

    return {
        "epic": epic,
        "stories": stories,
    }
