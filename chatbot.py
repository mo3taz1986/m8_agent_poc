import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from src.services.intake_service import process_input


def ask_chatbot(user_question: str):
    """
    Adapter between Streamlit UI and the current orchestration path.
    """
    return process_input(user_input=user_question, top_k=4)