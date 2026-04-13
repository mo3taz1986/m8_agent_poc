from __future__ import annotations

from typing import Callable, Dict

try:
    from langgraph.graph import END, StateGraph
    LANGGRAPH_AVAILABLE = True
except Exception:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class SimpleGraph:
    def __init__(self, nodes: Dict[str, Callable[[Dict], Dict]]) -> None:
        self.nodes = nodes

    def invoke(self, state: Dict) -> Dict:
        state = self.nodes["session"](state)
        state = self.nodes["question"](state)
        if state.get("route") == "done":
            return state

        state = self.nodes["classification"](state)
        return state


def build_orchestration_graph():
    from src.services.leader_agent import classification_node, question_node, session_node

    nodes = {
        "session": session_node,
        "question": question_node,
        "classification": classification_node,
    }

    if not LANGGRAPH_AVAILABLE:
        return SimpleGraph(nodes)

    graph = StateGraph(dict)
    graph.add_node("session", session_node)
    graph.add_node("question", question_node)
    graph.add_node("classification", classification_node)

    graph.set_entry_point("session")
    graph.add_edge("session", "question")

    def route_after_question(state: Dict) -> str:
        return "end" if state.get("route") == "done" else "classification"

    graph.add_conditional_edges(
        "question",
        route_after_question,
        {
            "classification": "classification",
            "end": END,
        },
    )
    graph.add_edge("classification", END)

    return graph.compile()