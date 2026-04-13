
from __future__ import annotations

from typing import Dict, Optional

from src.services.answer_service import ask_question
from src.services.ba_service import (
    approve_requirement_flow,
    continue_requirement_flow,
    generate_jira_payload_flow,
    get_session,
    revise_requirement_flow,
    send_to_jira_flow,
    start_requirement_flow,
)
from src.services.classification_service import classify_intent
from src.services.ambiguity_resolution_service import (
    build_ambiguity_response,
    create_pending_intent_id,
    resolve_ambiguous_followup,
)
from src.graph.orchestration_graph import build_orchestration_graph

PENDING_INTENT_STORE: Dict[str, Dict] = {}

CONCEPT_PREFIXES = (
    "what is ",
    "what are ",
    "define ",
    "explain ",
    "how does ",
    "how do ",
    "how should ",
    "what does ",
)

CONCEPT_PHRASES = (
    "usually work",
    "in technical context",
    "in business context",
    "technical context",
    "business context",
    "data context",
    "conceptually",
    "how it works",
)

EXPLICIT_REQUIREMENT_SIGNALS = (
    "we need",
    "i need",
    "build ",
    "create ",
    "implement ",
    "new requirement",
    "define a new requirement",
    "start requirement",
    "requirement for",
)

CONTEXT_SIGNALS = (
    "this document",
    "our document",
    "our docs",
    "architecture notes",
    "our notes",
    "retrieved context",
    "uploaded file",
    "this file",
    "this pdf",
    "this text",
    "from the doc",
    "from the document",
    "from our architecture",
)


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().strip().split())


def _looks_like_requirement_request(text: str) -> bool:
    normalized = _normalize(text)
    return any(signal in normalized for signal in EXPLICIT_REQUIREMENT_SIGNALS)


def _looks_like_context_question(text: str) -> bool:
    normalized = _normalize(text)
    return any(signal in normalized for signal in CONTEXT_SIGNALS)


def _looks_like_concept_question(text: str) -> bool:
    normalized = _normalize(text)

    if normalized.startswith(CONCEPT_PREFIXES):
        return True

    return any(phrase in normalized for phrase in CONCEPT_PHRASES)


def _decide_mode_from_input(user_input: str) -> str:
    if _looks_like_requirement_request(user_input):
        return "REQUIREMENT"

    if _looks_like_context_question(user_input):
        return "CONTEXT"

    if _looks_like_concept_question(user_input):
        return "CONCEPT"

    return "UNDECIDED"


class LeaderAgent:
    def __init__(self) -> None:
        self.graph = build_orchestration_graph()

    def handle_input(
        self,
        user_input: str,
        top_k: int = 4,
        session_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Dict:
        if action:
            return self._handle_action(session_id=session_id, action=action)

        if session_id:
            existing_session = get_session(session_id)
            if existing_session and existing_session.get("mode") == "REQUIREMENT":
                return continue_requirement_flow(session_id=session_id, user_input=user_input)

            pending_intent = PENDING_INTENT_STORE.get(session_id)
            if pending_intent:
                return self._handle_pending_ambiguity(
                    session_id=session_id,
                    user_input=user_input,
                    top_k=top_k,
                    pending_intent=pending_intent,
                )

        state = {
            "user_input": user_input,
            "top_k": top_k,
            "session_id": session_id,
            "response": None,
        }
        result = self.graph.invoke(state)
        return result["response"]

    def _handle_action(self, session_id: Optional[str], action: str) -> Dict:
        if not session_id:
            raise ValueError("session_id is required when using an action.")

        normalized_action = action.strip().upper()

        if normalized_action == "APPROVE":
            return approve_requirement_flow(session_id=session_id)

        if normalized_action == "REVISE":
            return revise_requirement_flow(session_id=session_id)

        if normalized_action == "GENERATE_JIRA":
            return generate_jira_payload_flow(session_id=session_id)

        if normalized_action == "SEND_TO_JIRA":
            return send_to_jira_flow(session_id=session_id)

        raise ValueError(f"Unsupported action: {action}")

    def _handle_pending_ambiguity(
        self,
        session_id: str,
        user_input: str,
        top_k: int,
        pending_intent: Dict,
    ) -> Dict:
        resolved_intent = resolve_ambiguous_followup(
            original_request=pending_intent["original_request"],
            followup=user_input,
        )
        original_request = pending_intent["original_request"]
        del PENDING_INTENT_STORE[session_id]

        if resolved_intent == "REQUIREMENT":
            return start_requirement_flow(user_input=original_request)

        answer_result = ask_question(question=original_request, top_k=top_k, mode="CONCEPT")
        return {
            "mode": "QUESTION",
            "status": "COMPLETED",
            "message": "Processed as knowledge question after routing clarification.",
            "session_id": session_id,
            "question_result": answer_result,
            "ba_result": None,
        }


def session_node(state: Dict) -> Dict:
    return state


def question_node(state: Dict) -> Dict:
    user_input = state["user_input"]
    session_id = state.get("session_id")
    top_k = state.get("top_k", 4)

    mode = _decide_mode_from_input(user_input)
    state["preclassified_mode"] = mode

    if mode == "CONCEPT":
        answer_result = ask_question(question=user_input, top_k=top_k, mode="CONCEPT")
        state["response"] = {
            "mode": "QUESTION",
            "status": "COMPLETED",
            "message": "Processed as knowledge question.",
            "session_id": session_id,
            "question_result": answer_result,
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    if mode == "CONTEXT":
        answer_result = ask_question(question=user_input, top_k=top_k, mode="CONTEXT")
        state["response"] = {
            "mode": "QUESTION",
            "status": "COMPLETED",
            "message": "Processed as context-aware question.",
            "session_id": session_id,
            "question_result": answer_result,
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    if mode == "REQUIREMENT":
        state["response"] = start_requirement_flow(user_input=user_input)
        state["route"] = "done"
        return state

    intent_result = classify_intent(user_input)
    state["intent_result"] = intent_result

    if intent_result["intent"] == "QUESTION":
        answer_result = ask_question(question=user_input, top_k=top_k, mode="CONTEXT")
        state["response"] = {
            "mode": "QUESTION",
            "status": "COMPLETED",
            "message": "Processed as knowledge question.",
            "session_id": session_id,
            "question_result": answer_result,
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    state["route"] = "classification"
    return state


def classification_node(state: Dict) -> Dict:
    user_input = state["user_input"]
    session_id = state.get("session_id")
    intent_result = state["intent_result"]
    intent = intent_result["intent"]

    if intent == "AMBIGUOUS":
        pending_id = create_pending_intent_id()
        PENDING_INTENT_STORE[pending_id] = {
            "original_request": user_input,
            "subtype": intent_result.get("subtype"),
            "ambiguity_reason": intent_result.get("ambiguity_reason"),
        }
        state["response"] = build_ambiguity_response(
            user_input=user_input,
            subtype=intent_result.get("subtype"),
            ambiguity_reason=intent_result.get("ambiguity_reason"),
            session_id=pending_id,
        )
        state["route"] = "done"
        return state

    if intent == "REQUIREMENT":
        state["response"] = start_requirement_flow(user_input=user_input)
        state["route"] = "done"
        return state

    if intent == "TASK":
        state["response"] = {
            "mode": "TASK",
            "status": "TASK_NOT_ENABLED",
            "message": (
                "Task-oriented request detected. "
                "Task execution is not enabled outside the approved execution flow."
            ),
            "session_id": session_id,
            "question_result": None,
            "ba_result": {
                "original_request": user_input,
                "next_step": "task_execution_not_available",
            },
        }
        state["route"] = "done"
        return state

    state["response"] = {
        "mode": "QUESTION",
        "status": "COMPLETED",
        "message": "Processed as knowledge question.",
        "session_id": session_id,
        "question_result": ask_question(question=user_input, top_k=state.get("top_k", 4), mode="CONTEXT"),
        "ba_result": None,
    }
    state["route"] = "done"
    return state