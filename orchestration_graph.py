from __future__ import annotations

from typing import Callable, Dict

try:
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except Exception:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


# ── SimpleGraph fallback ───────────────────────────────────────────────────
# Used when LangGraph is not installed. Executes the same 9-node sequence
# using the route field set by each node to decide the next step.

class SimpleGraph:
    """
    Fallback graph for environments where LangGraph is not installed.
    Executes nodes in sequence following the route field in state.
    Supports the full 11-step flow including ambiguity and deepening.
    """

    def __init__(self, nodes: Dict[str, Callable[[Dict], Dict]]) -> None:
        self.nodes = nodes

    def invoke(self, state: Dict) -> Dict:
        # If state already has a route set (e.g. "deepening" from an ambiguity
        # response), skip the entry nodes and jump directly to that step.
        entry_route = state.get("route")
        if entry_route == "deepening":
            state = self.nodes["deepening"](state)
            if state.get("route") == "done":
                return state
        else:
            # Step 1 — Session
            state = self.nodes["session"](state)

            # Step 2 — Question (pre-classification)
            state = self.nodes["question"](state)
            if state.get("route") == "done":
                return state

            # Step 3 — Classification (UNDECIDED inputs only)
            if state.get("route") == "classification":
                state = self.nodes["classification"](state)
                if state.get("route") == "done":
                    return state

            # Step 4 — Ambiguity (AMBIGUOUS intent only)
            if state.get("route") == "ambiguity":
                state = self.nodes["ambiguity"](state)
                if state.get("route") == "done":
                    return state

            # Step 5 — Deepening (after user responds to ambiguity question)
            if state.get("route") == "deepening":
                state = self.nodes["deepening"](state)
                if state.get("route") == "done":
                    return state

        # Step 6 — Meaning Agent (shape resolution)
        if state.get("route") == "meaning":
            state = self.nodes["meaning"](state)
            if state.get("route") == "done":
                return state

        # Step 7 — Metadata Agent (overlap check)
        if state.get("route") == "metadata":
            state = self.nodes["metadata"](state)

        # Step 8 — Context Agent (enrichment)
        if state.get("route") == "context":
            state = self.nodes["context"](state)

        # Step 9 — BA Agent (start requirement flow)
        if state.get("route") == "ba":
            state = self.nodes["ba"](state)

        return state


def build_orchestration_graph():
    from src.services.leader_agent import (
        entry_router_node,
        session_node,
        question_node,
        classification_node,
        ambiguity_node,
        deepening_node,
        meaning_node,
        metadata_node,
        context_node,
        ba_node,
    )

    nodes = {
        "session":        session_node,
        "question":       question_node,
        "classification": classification_node,
        "ambiguity":      ambiguity_node,
        "deepening":      deepening_node,
        "meaning":        meaning_node,
        "metadata":       metadata_node,
        "context":        context_node,
        "ba":             ba_node,
    }

    if not LANGGRAPH_AVAILABLE:
        return SimpleGraph(nodes)

    # ── LangGraph 9-node graph ─────────────────────────────────────────────
    graph = StateGraph(dict)

    # Register all nodes
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    # Entry point — router handles both normal flow and ambiguity-response
    # re-entry (where state already has route="deepening").
    graph.add_node("entry_router", entry_router_node)
    graph.set_entry_point("entry_router")

    graph.add_conditional_edges(
        "entry_router",
        lambda s: s.get("route", "session"),
        {
            "session":   "session",
            "deepening": "deepening",
        },
    )

    # session → question (always)
    graph.add_edge("session", "question")

    # question → conditional
    def route_after_question(state: Dict) -> str:
        return state.get("route", "done")

    graph.add_conditional_edges(
        "question",
        route_after_question,
        {
            "done":           END,
            "classification": "classification",
            "meaning":        "meaning",
        },
    )

    # classification → conditional
    def route_after_classification(state: Dict) -> str:
        return state.get("route", "done")

    graph.add_conditional_edges(
        "classification",
        route_after_classification,
        {
            "done":     END,
            "ambiguity":"ambiguity",
            "meaning":  "meaning",
        },
    )

    # ambiguity → done (returns clarifying question to user)
    graph.add_edge("ambiguity", END)

    # deepening → conditional (after user responds to ambiguity question)
    def route_after_deepening(state: Dict) -> str:
        return state.get("route", "done")

    graph.add_conditional_edges(
        "deepening",
        route_after_deepening,
        {
            "done":    END,
            "meaning": "meaning",
        },
    )

    # meaning → conditional
    def route_after_meaning(state: Dict) -> str:
        return state.get("route", "done")

    graph.add_conditional_edges(
        "meaning",
        route_after_meaning,
        {
            "done":     END,   # Meaning Agent returned deepening question
            "metadata": "metadata",
        },
    )

    # metadata → context (always — never blocks routing)
    graph.add_edge("metadata", "context")

    # context → ba (always — enrichment only)
    graph.add_edge("context", "ba")

    # ba → end
    graph.add_edge("ba", END)

    return graph.compile()
