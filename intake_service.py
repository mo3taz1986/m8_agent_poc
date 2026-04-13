from typing import Dict, Optional

from src.services.leader_agent import LeaderAgent

_LEADER = LeaderAgent()


def process_input(
    user_input: str,
    top_k: int = 4,
    session_id: Optional[str] = None,
    action: Optional[str] = None,
) -> Dict:
    """
    Thin live entry wrapper.

    This keeps /process aligned to the LeaderAgent so routing,
    ambiguity handling, question answering, and requirement
    orchestration all go through one control path.
    """
    return _LEADER.handle_input(
        user_input=user_input,
        top_k=top_k,
        session_id=session_id,
        action=action,
    )