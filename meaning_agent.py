from __future__ import annotations

from typing import Dict

from src.services.classification_service import (
    classify_intent,
    classify_requirement_subtype_strong,
)
from src.services.intent_deepening_service import (
    build_intent_deepening_response,
    should_trigger_intent_deepening,
)


class MeaningAgent:
    """
    Phase 2 meaning layer.

    Responsibility:
    - inspect requirement-like input
    - decide whether one deepening question is needed
    - resolve requirement shape using the stronger classification path
    - return a simple, structured result to the leader
    """

    def evaluate(self, user_input: str, session_id: str) -> Dict:
        intent_result = classify_intent(user_input)
        intent = intent_result.get("intent", "QUESTION")

        if intent != "REQUIREMENT":
            return {
                "mode": intent,
                "needs_deepening": False,
                "shape_locked": False,
                "intent_result": intent_result,
                "shape_result": None,
                "response": None,
            }

        if should_trigger_intent_deepening(user_input, intent_result):
            response = build_intent_deepening_response(
                user_input=user_input,
                intent_result=intent_result,
                session_id=session_id,
            )
            return {
                "mode": "INTENT_DEEPENING",
                "needs_deepening": True,
                "shape_locked": False,
                "intent_result": intent_result,
                "shape_result": None,
                "response": response,
            }

        shape_result = self.resolve_shape(user_input)
        return {
            "mode": "REQUIREMENT",
            "needs_deepening": False,
            "shape_locked": shape_result.get("is_locked", False),
            "intent_result": intent_result,
            "shape_result": shape_result,
            "response": None,
        }

    def evaluate_after_deepening(self, combined_request: str) -> Dict:
        shape_result = self.resolve_shape(combined_request)
        return {
            "mode": "REQUIREMENT",
            "needs_deepening": False,
            "shape_locked": shape_result.get("is_locked", False),
            "intent_result": {"intent": "REQUIREMENT"},
            "shape_result": shape_result,
            "response": None,
        }

    @staticmethod
    def resolve_shape(user_input: str) -> Dict:
        subtype_result = classify_requirement_subtype_strong(user_input)
        subtype = subtype_result.get("subtype", "generic_business_request")
        confidence = float(
            subtype_result.get("confidence", subtype_result.get("subtype_confidence", 0.0)) or 0.0
        )

        label_map = {
            "interactive_dashboard": "dashboard requirement",
            "reporting_output": "reporting requirement",
            "structured_extract": "structured extract requirement",
            "data_view": "data view requirement",
            "data_pipeline": "data pipeline requirement",
            "integration_request": "integration requirement",
            "workflow_automation": "workflow requirement",
            "analytical_model": "analytical model requirement",
            "generic_business_request": "new capability requirement",
        }

        return {
            "resolved_category": subtype,
            "resolved_label": label_map.get(subtype, "new capability requirement"),
            "confidence": confidence,
            "is_locked": subtype != "generic_business_request" and confidence >= 0.60,
            "method": subtype_result.get("method", "classification_service"),
            "raw_result": subtype_result,
        }

    @staticmethod
    def build_category_opening(shape_result: Dict) -> str:
        label = shape_result.get("resolved_label", "new capability requirement")
        return f"I'll treat this as a new {label} and start structuring the requirement."

    @staticmethod
    def enrich_request_with_shape(user_request: str, shape_result: Dict) -> str:
        subtype = shape_result.get("resolved_category", "generic_business_request")

        prefix_map = {
            "interactive_dashboard": "Dashboard requirement:",
            "reporting_output": "Reporting requirement:",
            "structured_extract": "Structured extract requirement:",
            "data_view": "Database view requirement:",
            "data_pipeline": "Data pipeline requirement:",
            "integration_request": "Integration requirement:",
            "workflow_automation": "Workflow requirement:",
            "analytical_model": "Analytical model requirement:",
        }

        prefix = prefix_map.get(subtype)
        if not prefix:
            return user_request

        normalized = (user_request or "").strip().lower()
        if normalized.startswith(prefix.lower()):
            return user_request

        return f"{prefix} {user_request}"
