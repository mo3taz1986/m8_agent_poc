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
from src.services.meaning_agent import MeaningAgent
from src.agents.metadata_agent import MetadataAgent
from src.agents.context_agent import ContextAgent
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

# Stakeholder subjects — business roles/groups that express needs on behalf of others.
STAKEHOLDER_SUBJECTS = (
    "leadership",
    "leaders",
    "finance",
    "finance team",
    "product team",
    "product managers",
    "operations",
    "operations team",
    "the business",
    "business",
    "executives",
    "management",
    "the team",
    "our team",
    "analytics team",
    "data team",
    "sales team",
    "marketing team",
    "the org",
    "the organization",
)

STAKEHOLDER_NEED_VERBS = (
    " needs ",
    " need ",
    " requires ",
    " require ",
    " wants ",
    " want ",
)

CAPABILITY_NOUNS = (
    "visibility",
    "reporting",
    "dashboard",
    "dashboards",
    "report",
    "reports",
    "tracking",
    "insight",
    "insights",
    "monitoring",
    "metrics",
    "kpis",
    "pipeline",
    "feed",
    "integration",
    "workflow",
    "extract",
    "view",
    "dataset",
    "model",
    "scorecard",
    "analysis",
    "breakdown",
    "summary",
    "access",
    "performance",
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


def _looks_like_stakeholder_requirement(text: str) -> bool:
    """
    Detect third-person stakeholder requirement statements of the form:
    '[stakeholder subject] needs/requires [capability noun]'
    """
    normalized = _normalize(text)

    if normalized.endswith("?"):
        return False

    question_starters = (
        "what ", "how ", "why ", "when ", "where ", "who ", "which ",
        "is ", "are ", "do ", "does ", "did ", "can ", "could ", "should ",
        "would ", "will ",
    )
    if any(normalized.startswith(qs) for qs in question_starters):
        return False

    for subject in STAKEHOLDER_SUBJECTS:
        if not normalized.startswith(subject):
            continue
        remainder = normalized[len(subject):]
        for verb in STAKEHOLDER_NEED_VERBS:
            if not remainder.startswith(verb):
                continue
            after_verb = remainder[len(verb):]
            if any(cap in after_verb for cap in CAPABILITY_NOUNS):
                return True

    return False


def _decide_mode_from_input(user_input: str) -> str:
    if _looks_like_requirement_request(user_input):
        return "REQUIREMENT"
    if _looks_like_context_question(user_input):
        return "CONTEXT"
    if _looks_like_concept_question(user_input):
        return "CONCEPT"
    if _looks_like_stakeholder_requirement(user_input):
        return "REQUIREMENT"
    return "UNDECIDED"


def _route_requirement_through_meaning(
    meaning_agent: MeaningAgent,
    user_input: str,
    session_id: Optional[str],
    after_deepening: bool = False,
    metadata_agent: Optional[MetadataAgent] = None,
) -> Dict:
    """
    Central helper that runs user_input through the Meaning Agent and
    decides what happens next. All three requirement entry points
    (question_node, classification_node, _handle_pending_ambiguity) call
    this instead of start_requirement_flow directly.

    Three outcomes:
    1. Needs deepening — Meaning Agent wants one clarifying question first.
       Return the deepening question response. BA does not start yet.
    2. Shape resolved — enrich the request with the locked category prefix
       and start the BA flow with shape_result stored on the session.
    3. Shape not locked (low confidence) — fall through to BA with best
       available shape rather than blocking the user indefinitely.

    after_deepening=True skips the deepening check — used when the request
    already went through ambiguity resolution before reaching here.
    """
    if after_deepening:
        meaning = meaning_agent.evaluate_after_deepening(user_input)
    else:
        meaning = meaning_agent.evaluate(user_input, session_id or "")

    # Meaning Agent wants one clarifying question before resolving shape.
    if meaning.get("mode") == "INTENT_DEEPENING" and meaning.get("response"):
        return meaning["response"]

    # Shape resolved — enrich the request so BA's infer_request_type
    # picks up the locked category from the start.
    shape_result = meaning.get("shape_result")
    if shape_result:
        enriched_input = MeaningAgent.enrich_request_with_shape(user_input, shape_result)
    else:
        enriched_input = user_input

    # Run Metadata Agent if available and shape is locked.
    metadata_result = None
    if metadata_agent and shape_result:
        resolved_category = shape_result.get("resolved_category", "generic_business_request")
        # Build a minimal requirement_state for the metadata lookup using
        # whatever signals are already available from the original request.
        lookup_state = {"original_request": user_input}
        metadata_result = metadata_agent.evaluate(
            requirement_state=lookup_state,
            resolved_category=resolved_category,
        )

    return start_requirement_flow(
        user_input=enriched_input,
        shape_result=shape_result,
        metadata_result=metadata_result,
    )


class LeaderAgent:
    def __init__(self) -> None:
        self.graph = build_orchestration_graph()
        # Meaning Agent is instantiated once on the Leader and shared across
        # all calls. It is stateless — safe to reuse.
        self._meaning_agent = MeaningAgent()
        # Metadata Agent validates against the enterprise asset store.
        # Also stateless — safe to share.
        self._metadata_agent = MetadataAgent()
        # Context Agent owns retrieval — injected into graph state so
        # question_node can call it without going through answer_service.
        self._context_agent = ContextAgent()

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

            # Session ID provided but session wiped (server restart).
            # Recover gracefully by starting a fresh session through the
            # Meaning Agent rather than crashing with a 500.
            if not existing_session:
                fresh = _route_requirement_through_meaning(
                    meaning_agent=self._meaning_agent,
                    user_input=user_input,
                    session_id=None,
                    metadata_agent=self._metadata_agent,
                )
                fresh["_session_recovered"] = True
                fresh["message"] = (
                    "Your previous session was no longer available. "
                    "I've started a fresh session with your input."
                )
                return fresh

        state = {
            "user_input": user_input,
            "top_k": top_k,
            "session_id": session_id,
            # Pass the Meaning Agent instance into graph state so nodes
            # can call it without re-instantiating.
            "meaning_agent": self._meaning_agent,
            "metadata_agent": self._metadata_agent,
            "context_agent": self._context_agent,
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
            # Ambiguity resolution already served as the deepening question.
            # Call evaluate_after_deepening to skip the deepening check and
            # go straight to shape resolution then BA.
            return _route_requirement_through_meaning(
                meaning_agent=self._meaning_agent,
                user_input=original_request,
                session_id=session_id,
                after_deepening=True,
                metadata_agent=self._metadata_agent,
            )

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
    meaning_agent: MeaningAgent = state["meaning_agent"]

    mode = _decide_mode_from_input(user_input)
    state["preclassified_mode"] = mode

    context_agent: ContextAgent = state.get("context_agent") or ContextAgent()

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
        answer_result = ask_question(
            question=user_input, top_k=top_k, mode="CONTEXT",
            context_agent=context_agent,
        )
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
        # Pre-classifier confirmed requirement — route through Meaning Agent
        # so shape is resolved before BA starts.
        state["response"] = _route_requirement_through_meaning(
            meaning_agent=meaning_agent,
            user_input=user_input,
            session_id=session_id,
            metadata_agent=state.get("metadata_agent"),
        )
        state["route"] = "done"
        return state

    intent_result = classify_intent(user_input)
    state["intent_result"] = intent_result

    if intent_result["intent"] == "QUESTION":
        answer_result = ask_question(
            question=user_input, top_k=top_k, mode="CONTEXT",
            context_agent=context_agent,
        )
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
    meaning_agent: MeaningAgent = state["meaning_agent"]

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
        # Classification confirmed requirement — route through Meaning Agent
        # so shape is resolved before BA starts.
        state["response"] = _route_requirement_through_meaning(
            meaning_agent=meaning_agent,
            user_input=user_input,
            session_id=session_id,
            metadata_agent=state.get("metadata_agent"),
        )
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
        "question_result": ask_question(
            question=user_input,
            top_k=state.get("top_k", 4),
            mode="CONTEXT",
            context_agent=state.get("context_agent"),
        ),
        "ba_result": None,
    }
    state["route"] = "done"
    return state
