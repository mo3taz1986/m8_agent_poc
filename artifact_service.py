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
    """
    Produces a clean, normalised fallback epic object name when the LLM call
    fails or returns an out-of-range title.

    Strategy:
    1. Prefer business_objective over raw source_request — it is already
       a cleaned, intent-focused sentence produced by the BA agent.
    2. Strip sentence-template prefixes and raw user phrasing artifacts
       (e.g. "requirement:", "We new", "The request originated from:").
    3. Detect a delivery type keyword from the combined text.
    4. Extract the noun subject by removing fillers and delivery-type words.
    5. Title-case and truncate to produce a Jira-safe name.
    """
    objective = safe_text(requirement_document.get("business_objective"))
    source    = safe_text(requirement_document.get("source_request"))

    # Always use source_request — it is the clearest, shortest signal for naming.
    # business_objective is a long sentence and produces noisy titles in the fallback.
    base = source if source != "Needs clarification" else objective
    base = clean_text(base)

    # Strip common sentence-template prefixes that bleed in from generated text
    strip_prefixes = [
        r"the request originated from\s*[:\-]?\s*['\"]?",
        r"the primary business objective is\s*[:\-]?\s*",
        r"[a-z ,]+requirement[s]?\s*[:\-]\s*",   # "Data pipeline requirement:"
        r"we need (a |an |the )?",
        r"build (a |an |the )?",
        r"create (a |an |the )?",
        r"develop (a |an |the )?",
        r"implement (a |an |the )?",
        r"new\s+",
    ]
    for pattern in strip_prefixes:
        base = re.sub(pattern, "", base, flags=re.IGNORECASE).strip()

    # Detect delivery type from the full combined text before further stripping
    delivery_type_map = [
        (r"\bpipeline\b",     "Pipeline"),
        (r"\bdashboard\b",    "Dashboard"),
        (r"\breport\b",       "Report"),
        (r"\bmodel\b",        "Model"),
        (r"\bworkflow\b",     "Workflow"),
        (r"\bintegration\b",  "Integration"),
        (r"\bautomation\b",   "Automation"),
        (r"\bextract\b",      "Extract"),
        (r"\bview\b",         "View"),
    ]
    detected_type = ""
    combined_text = f"{base} {source} {objective}".lower()
    for pattern, label in delivery_type_map:
        if re.search(pattern, combined_text):
            detected_type = label
            break

    # Strip filler and structural words to isolate the business subject noun
    fillers = {
        "build", "create", "develop", "implement", "generate",
        "need", "needs", "want", "wants", "help", "please",
        "should", "would", "could", "ability", "capability",
        "allow", "allows", "leadership", "team", "users", "user",
        "system", "solution", "it", "this", "that", "the", "a", "an",
        "to", "for", "of", "and", "with", "by", "in", "on", "at",
        "new", "better", "improved", "fast", "faster",
        "requirement", "requirements",
        # delivery-type words handled separately — strip here to avoid duplication
        "pipeline", "dashboard", "report", "model", "workflow",
        "integration", "automation", "extract", "view",
    }

    words = []
    for word in base.split():
        cleaned = re.sub(r"[^a-zA-Z0-9\-]", "", word)
        if not cleaned:
            continue
        if cleaned.lower() in fillers:
            continue
        words.append(cleaned.capitalize())

    subject = " ".join(words[:4]).strip()
    if not subject:
        subject = "Business Capability"

    name = f"{subject} {detected_type}".strip() if detected_type else subject
    return truncate_text(name, 60)


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
Convert the following user request into a clean Jira Epic title.

The user said: "{source}"

Rules:
- Extract the core business subject from what the user asked for (e.g. "product profitability", "RPM data", "customer churn")
- Append the correct delivery type: Dashboard, Pipeline, Report, Model, Workflow, Integration, Automation, Extract, or View
- 3 to 8 words total
- Title Case
- Noun phrase only — no verbs, no filler words
- No punctuation except spaces and hyphens
- Return ONLY the Jira title. Nothing else.

Examples:
"we need a dashboard for product profitability by region" -> Product Profitability Dashboard by Region
"build me a pipeline to move RPM data to the warehouse" -> RPM Data Pipeline to Warehouse
"create a monthly P&L consolidation report" -> Monthly P&L Consolidation Report
"we need something to track supplier KPIs" -> Supplier KPI Tracking Dashboard
"predict which customers are going to churn" -> Customer Churn Prediction Model
"dashboard for product profitability" -> Product Profitability Dashboard
""".strip()

        response = _client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=60,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )

        title = ""
        if getattr(response, "content", None):
            first_block = response.content[0]
            title = getattr(first_block, "text", "") or ""

        title = clean_text(title).replace('"', "").strip()

        # Reject if raw input phrasing or verb-led output leaked through
        bad_patterns = [
            r"\bwe\b", r"\bi\b", r"\bneed\b", r"\bbuild\b",
            r"\bcreate\b", r"\brequirement[s]?\b",
            r"^enable\b", r"^allow\b", r"^help\b",
            r"^implement\b", r"^develop\b", r"^generate\b",
        ]
        for bad in bad_patterns:
            if re.search(bad, title, flags=re.IGNORECASE):
                raise ValueError(f"Epic title contains raw input phrasing: '{title}'")

        word_count = len(title.split())
        if not title or word_count < 3 or word_count > 14:
            raise ValueError(f"Epic title out of range: '{title}'")

        title = truncate_text(title, 80)
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
