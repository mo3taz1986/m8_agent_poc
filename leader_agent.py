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
    resolve_ambiguous_followup,
)
from src.services.meaning_agent import MeaningAgent
from src.agents.metadata_agent import MetadataAgent
from src.agents.context_agent import ContextAgent
from src.graph.orchestration_graph import build_orchestration_graph

# ── Routing signal constants ───────────────────────────────────────────────

CONCEPT_PREFIXES = (
    "what is ", "what are ", "define ", "explain ",
    "how does ", "how do ", "how should ", "what does ",
)

CONCEPT_PHRASES = (
    "usually work", "in technical context", "in business context",
    "technical context", "business context", "data context",
    "conceptually", "how it works",
)

EXPLICIT_REQUIREMENT_SIGNALS = (
    "we need", "i need", "build ", "create ", "implement ",
    "new requirement", "define a new requirement",
    "start requirement", "requirement for",
)

CONTEXT_SIGNALS = (
    "this document", "our document", "our docs", "architecture notes",
    "our notes", "retrieved context", "uploaded file", "this file",
    "this pdf", "this text", "from the doc", "from the document",
    "from our architecture",
    "in the policy", "the policy", "the policy document",
    "per the policy", "according to the policy",
    "policy say", "policy mention", "policy require",
    "policy state", "policy cover", "does the policy",
    "what does the policy", "retention policy", "access policy",
    "quality policy", "data policy", "governance policy",
)

STAKEHOLDER_SUBJECTS = (
    "leadership", "leaders", "finance", "finance team", "product team",
    "product managers", "operations", "operations team", "the business",
    "business", "executives", "management", "the team", "our team",
    "analytics team", "data team", "sales team", "marketing team",
    "the org", "the organization",
)

STAKEHOLDER_NEED_VERBS = (
    " needs ", " need ", " requires ", " require ", " wants ", " want ",
)

CAPABILITY_NOUNS = (
    "visibility", "reporting", "dashboard", "dashboards", "report",
    "reports", "tracking", "insight", "insights", "monitoring", "metrics",
    "kpis", "pipeline", "feed", "integration", "workflow", "extract",
    "view", "dataset", "model", "scorecard", "analysis", "breakdown",
    "summary", "access", "performance",
)


# ── Input signal helpers ───────────────────────────────────────────────────

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


# ── LeaderAgent ────────────────────────────────────────────────────────────

class LeaderAgent:
    """
    Orchestration layer. Owns flow, gates every step, assembles
    final response from agent outputs.

    All specialist agents are instantiated once and injected into
    graph state — stateless, safe to share across requests.
    """

    def __init__(self) -> None:
        self._meaning_agent  = MeaningAgent()
        self._metadata_agent = MetadataAgent()
        self._context_agent  = ContextAgent()
        self.graph = build_orchestration_graph()

    def handle_input(
        self,
        user_input: str,
        top_k: int = 4,
        session_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> Dict:
        # Actions bypass the graph entirely — they operate on an existing
        # session and don't need routing.
        if action:
            return self._handle_action(session_id=session_id, action=action)

        if session_id:
            existing_session = get_session(session_id)

            # Active REQUIREMENT session — continue without re-routing.
            if existing_session and existing_session.get("mode") == "REQUIREMENT":
                return continue_requirement_flow(
                    session_id=session_id, user_input=user_input
                )

            # Active AMBIGUOUS session — the user is responding to a
            # clarifying question. Route through deepening_node with
            # the original request from the persisted ambiguity session.
            if existing_session and existing_session.get("mode") == "AMBIGUOUS":
                return self._handle_ambiguity_response(
                    session_id=session_id,
                    user_input=user_input,
                    top_k=top_k,
                    ambiguity_session=existing_session,
                )

            # Session ID provided but session wiped (server restart).
            # Recover gracefully — route the input as a fresh request.
            if not existing_session:
                fresh = self._invoke_graph(user_input, top_k, session_id=None)
                fresh["_session_recovered"] = True
                fresh["message"] = (
                    "Your previous session was no longer available. "
                    "I've started a fresh session with your input."
                )
                return fresh

        return self._invoke_graph(user_input, top_k, session_id=session_id)

    def _handle_ambiguity_response(
        self,
        session_id: str,
        user_input: str,
        top_k: int,
        ambiguity_session: Dict,
    ) -> Dict:
        """
        Called when the user responds to an ambiguity clarifying question.
        Deletes the ambiguity session (consumed), then routes through the
        graph with deepening_node as the entry target.
        """
        from src.services.ba_service import session_store as ba_session_store
        # Consume the ambiguity session — it is single-use
        ba_session_store.delete(session_id)

        original_request = ambiguity_session.get("original_request", user_input)
        ambiguity_reason = ambiguity_session.get("ambiguity_reason")

        state = {
            "user_input":               user_input,
            "top_k":                    top_k,
            "session_id":               None,  # fresh session will be created by ba_node
            "meaning_agent":            self._meaning_agent,
            "metadata_agent":           self._metadata_agent,
            "context_agent":            self._context_agent,
            "response":                 None,
            # Inject pending state for deepening_node
            "pending_original_request": original_request,
            "pending_ambiguity_reason": ambiguity_reason,
            "after_deepening":          False,
            # Signal to the graph to start at deepening_node
            "route":                    "deepening",
        }

        # Invoke only deepening_node → meaning → metadata → context → ba
        # by bypassing the session/question/classification nodes
        from src.graph.orchestration_graph import build_orchestration_graph
        result = self.graph.invoke(state)
        return result["response"]

    def _invoke_graph(
        self, user_input: str, top_k: int, session_id: Optional[str]
    ) -> Dict:
        state = {
            "user_input":     user_input,
            "top_k":          top_k,
            "session_id":     session_id,
            "meaning_agent":  self._meaning_agent,
            "metadata_agent": self._metadata_agent,
            "context_agent":  self._context_agent,
            "response":       None,
            # Ambiguity state — populated by ambiguity_node, consumed by
            # deepening_node. Replaces the old PENDING_INTENT_STORE dict.
            "pending_original_request": None,
            "pending_ambiguity_reason": None,
            "after_deepening": False,
        }
        result = self.graph.invoke(state)
        return result["response"]

    def _handle_action(self, session_id: Optional[str], action: str) -> Dict:
        if not session_id:
            raise ValueError("session_id is required when using an action.")

        normalized = action.strip().upper()

        if normalized == "APPROVE":
            return approve_requirement_flow(session_id=session_id)
        if normalized == "REVISE":
            return revise_requirement_flow(session_id=session_id)
        if normalized == "GENERATE_JIRA":
            return generate_jira_payload_flow(session_id=session_id)
        if normalized == "SEND_TO_JIRA":
            return send_to_jira_flow(session_id=session_id)

        raise ValueError(f"Unsupported action: {action}")


# ── Node 1 — Session ───────────────────────────────────────────────────────

def entry_router_node(state: Dict) -> Dict:
    """
    First node in the LangGraph graph. Routes to session_node for
    normal inputs, or directly to deepening_node when the state
    already has route="deepening" (ambiguity response re-entry path).
    The route field is set by _handle_ambiguity_response before invoking.
    """
    if state.get("route") == "deepening":
        return state  # LangGraph conditional edge will route to deepening
    # Normal path — clear any stale route and proceed to session
    state["route"] = "session"
    return state


def session_node(state: Dict) -> Dict:
    """
    Entry node. Currently a passthrough — session continuation and
    recovery are handled in handle_input before the graph is invoked.
    Placeholder for Phase 2 when Session Agent is fully extracted.
    """
    return state


# ── Node 2 — Question ─────────────────────────────────────────────────────

def question_node(state: Dict) -> Dict:
    """
    Pre-classify the input using deterministic signal matching.
    Exits the graph immediately for CONCEPT and CONTEXT questions.
    Routes REQUIREMENT directly to meaning_node.
    Falls through to classification_node for UNDECIDED inputs.
    """
    user_input    = state["user_input"]
    session_id    = state.get("session_id")
    top_k         = state.get("top_k", 4)
    context_agent = state.get("context_agent") or ContextAgent()

    mode = _decide_mode_from_input(user_input)
    state["preclassified_mode"] = mode

    if mode == "CONCEPT":
        state["response"] = {
            "mode": "QUESTION", "status": "COMPLETED",
            "message": "Processed as knowledge question.",
            "session_id": session_id,
            "question_result": ask_question(
                question=user_input, top_k=top_k, mode="CONCEPT"
            ),
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    if mode == "CONTEXT":
        state["response"] = {
            "mode": "QUESTION", "status": "COMPLETED",
            "message": "Processed as context-aware question.",
            "session_id": session_id,
            "question_result": ask_question(
                question=user_input, top_k=top_k, mode="CONTEXT",
                context_agent=context_agent,
            ),
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    if mode == "REQUIREMENT":
        # Skip classification — pre-classifier already confirmed requirement.
        state["route"] = "meaning"
        return state

    # Run classification for UNDECIDED inputs
    intent_result = classify_intent(user_input)
    state["intent_result"] = intent_result

    if intent_result["intent"] == "QUESTION":
        state["response"] = {
            "mode": "QUESTION", "status": "COMPLETED",
            "message": "Processed as knowledge question.",
            "session_id": session_id,
            "question_result": ask_question(
                question=user_input, top_k=top_k, mode="CONTEXT",
                context_agent=context_agent,
            ),
            "ba_result": None,
        }
        state["route"] = "done"
        return state

    state["route"] = "classification"
    return state


# ── Node 3 — Classification ────────────────────────────────────────────────

def classification_node(state: Dict) -> Dict:
    """
    Routes REQUIREMENT to meaning_node, AMBIGUOUS to ambiguity_node,
    TASK to a not-enabled response, everything else to Q&A.
    """
    user_input    = state["user_input"]
    session_id    = state.get("session_id")
    intent_result = state["intent_result"]
    intent        = intent_result["intent"]

    if intent == "AMBIGUOUS":
        # Store the original request in state so ambiguity_node can build
        # the clarifying question, and deepening_node can use it after the
        # user responds. Replaces PENDING_INTENT_STORE.
        state["pending_original_request"] = user_input
        state["pending_ambiguity_reason"]  = intent_result.get("ambiguity_reason")
        state["route"] = "ambiguity"
        return state

    if intent == "REQUIREMENT":
        state["route"] = "meaning"
        return state

    if intent == "TASK":
        state["response"] = {
            "mode": "TASK", "status": "TASK_NOT_ENABLED",
            "message": (
                "Task-oriented request detected. "
                "Task execution is not enabled outside the approved execution flow."
            ),
            "session_id": session_id,
            "question_result": None,
            "ba_result": {"original_request": user_input,
                          "next_step": "task_execution_not_available"},
        }
        state["route"] = "done"
        return state

    # Default — treat as knowledge question
    state["response"] = {
        "mode": "QUESTION", "status": "COMPLETED",
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


# ── Node 4 — Ambiguity ────────────────────────────────────────────────────

def ambiguity_node(state: Dict) -> Dict:
    """
    Builds and returns a single clarifying question when intent is ambiguous.

    Persists the pending original request to the session store using a
    dedicated AMBIGUOUS mode session. On the next turn, handle_input detects
    mode == "AMBIGUOUS" in the session and routes through deepening_node.
    This replaces the old PENDING_INTENT_STORE dict pattern.
    """
    from src.services.ba_service import session_store
    from src.services.session_store import SessionStore

    user_input               = state["user_input"]
    session_id               = state.get("session_id")
    pending_original_request = state.get("pending_original_request", user_input)
    ambiguity_reason         = state.get("pending_ambiguity_reason")
    intent_result            = state.get("intent_result", {})

    # Create a new session ID for this ambiguity interaction
    ambiguity_session_id = session_store.create_session_id()

    # Persist the pending state so handle_input can detect it on next turn
    session_store.set(ambiguity_session_id, {
        "mode":                    "AMBIGUOUS",
        "original_request":        pending_original_request,
        "ambiguity_reason":        ambiguity_reason,
        "subtype":                 intent_result.get("subtype"),
    })

    response = build_ambiguity_response(
        user_input=pending_original_request,
        subtype=intent_result.get("subtype"),
        ambiguity_reason=ambiguity_reason,
        session_id=ambiguity_session_id,
    )

    state["response"] = response
    state["route"]    = "done"
    return state


# ── Node 5 — Deepening ────────────────────────────────────────────────────

def deepening_node(state: Dict) -> Dict:
    """
    Called after the user responds to an ambiguity clarification.
    Resolves the follow-up against the original request and routes:
      - REQUIREMENT → meaning_node
      - QUESTION    → Q&A with CONTEXT mode (no hallucination)
    """
    user_input               = state["user_input"]
    session_id               = state.get("session_id")
    top_k                    = state.get("top_k", 4)
    original_request         = state.get("pending_original_request", user_input)

    resolved = resolve_ambiguous_followup(
        original_request=original_request,
        followup=user_input,
    )

    if resolved == "REQUIREMENT":
        # Deepening already served as the clarification step.
        # Skip the deepening check inside the Meaning Agent.
        state["after_deepening"]  = True
        state["user_input"]       = original_request
        state["route"]            = "meaning"
        return state

    # Resolved as question — use CONTEXT mode to avoid hallucination
    state["response"] = {
        "mode": "QUESTION", "status": "COMPLETED",
        "message": "Processed as knowledge question after routing clarification.",
        "session_id": session_id,
        "question_result": ask_question(
            question=original_request,
            top_k=top_k,
            mode="CONTEXT",
            context_agent=state.get("context_agent"),
        ),
        "ba_result": None,
    }
    state["route"] = "done"
    return state


# ── Node 6 — Meaning ──────────────────────────────────────────────────────

def meaning_node(state: Dict) -> Dict:
    """
    Runs the Meaning Agent to resolve delivery shape and confidence.
    If the agent wants one deepening question (low confidence / vague input)
    it returns the deepening response immediately.
    Otherwise enriches the request and routes to metadata_node.
    """
    user_input     = state["user_input"]
    session_id     = state.get("session_id")
    meaning_agent  = state.get("meaning_agent") or MeaningAgent()
    after_deepening = state.get("after_deepening", False)

    if after_deepening:
        meaning = meaning_agent.evaluate_after_deepening(user_input)
    else:
        meaning = meaning_agent.evaluate(user_input, session_id or "")

    # Meaning Agent wants one clarifying question before resolving shape.
    if meaning.get("mode") == "INTENT_DEEPENING" and meaning.get("response"):
        state["response"] = meaning["response"]
        state["route"]    = "done"
        return state

    # Shape resolved — store on state for metadata_node and ba_node.
    shape_result = meaning.get("shape_result")
    if shape_result:
        enriched = MeaningAgent.enrich_request_with_shape(user_input, shape_result)
        state["user_input"]   = enriched
        state["shape_result"] = shape_result
    else:
        state["shape_result"] = None

    state["route"] = "metadata"
    return state


# ── Node 7 — Metadata ─────────────────────────────────────────────────────

def metadata_node(state: Dict) -> Dict:
    """
    Runs the Metadata Agent to check for existing asset overlap.
    Result is stored on state and passed to ba_node.
    Never influences routing — always proceeds to context_node.
    """
    user_input      = state["user_input"]
    shape_result    = state.get("shape_result")
    metadata_agent  = state.get("metadata_agent") or MetadataAgent()

    metadata_result = None
    if shape_result:
        resolved_category = shape_result.get("resolved_category", "generic_business_request")
        metadata_result = metadata_agent.evaluate(
            requirement_state={"original_request": user_input},
            resolved_category=resolved_category,
        )

    state["metadata_result"] = metadata_result
    state["route"]           = "context"
    return state


# ── Node 8 — Context ──────────────────────────────────────────────────────

def context_node(state: Dict) -> Dict:
    """
    Context Agent enrichment — RAG retrieval to ground the BA session.
    Enrichment only: does not influence routing decisions.
    Currently a lightweight pass-through that stores retrieval signals
    for the BA Agent to reference. Full enrichment is a Phase 2 item
    once the Context Agent extraction is complete.
    """
    # Retrieval is called by answer_service during Q&A — for the
    # requirement flow we store a placeholder so ba_node knows context
    # enrichment ran. Full context injection into BA artifacts is Phase 2.
    state["context_enrichment"] = {"status": "deferred_to_ba_service"}
    state["route"] = "ba"
    return state


# ── Node 9 — BA ───────────────────────────────────────────────────────────

def ba_node(state: Dict) -> Dict:
    """
    Starts the BA requirement flow with the resolved shape and metadata.
    This is the final node in the requirement path — response is set here.
    """
    user_input      = state["user_input"]
    shape_result    = state.get("shape_result")
    metadata_result = state.get("metadata_result")

    response = start_requirement_flow(
        user_input=user_input,
        shape_result=shape_result,
        metadata_result=metadata_result,
    )

    state["response"] = response
    state["route"]    = "done"
    return state
