from typing import Dict, Optional
from uuid import uuid4

from src.services.clarification_service import (
    initialize_requirement_state,
    build_interpreted_summary,
    build_reasoning_summary,
)
from src.services.artifact_service import (
    generate_requirement_document,
    generate_epic_and_stories,
)
from src.services.jira_service import (
    build_execution_package,
    build_jira_payload,
    submit_jira_payload,
)
from src.services.decision_engine import decide_next_step
from src.services.revision_engine import apply_revision_feedback
from src.services.answer_quality_service import is_weak_answer, build_weak_answer_message
from src.services.meaning_interpreter import interpret_clarification_answer
from src.services.clarification_response_builder import build_clarification_feedback

SESSION_STORE: Dict[str, Dict] = {}


def create_session_id() -> str:
    return str(uuid4())


def _build_next_step_guidance(stage: str) -> str:
    if stage == "clarification":
        return "Answer the current question and I will refine the requirement further."
    if stage == "review_ready":
        return "Review the generated requirement package and decide whether to approve it or request revision."
    if stage == "execution_ready":
        return "The requirement package is approved and ready to be transformed into an execution payload."
    if stage == "jira_payload_ready":
        return "Review the Jira payload preview and send it to Jira when ready."
    if stage == "jira_submitted":
        return "The work package has been submitted to Jira successfully."
    return "Continue the workflow."


def build_ba_payload(
    stage: str,
    requirement_state: Dict,
    approval_status: str,
    requirement_document: Optional[Dict] = None,
    delivery_artifacts: Optional[Dict] = None,
    execution_package: Optional[Dict] = None,
    jira_payload: Optional[Dict] = None,
    jira_submission_result: Optional[Dict] = None,
    clarification_feedback: Optional[Dict] = None,
) -> Dict:
    interpreted_summary = build_interpreted_summary(requirement_state)
    reasoning_summary = build_reasoning_summary(requirement_state)
    decision = decide_next_step(requirement_state)

    if stage in {"review_ready", "execution_ready", "jira_payload_ready", "jira_submitted"}:
        current_field = None
        current_field_label = None
        current_question = None
        current_question_reason = None
    else:
        current_field = decision["question_field"]
        current_field_label = decision["question_field_label"]
        current_question = decision["next_question"]
        current_question_reason = decision["reason"]

    return {
        "stage": stage,
        "requirement_state": requirement_state,
        "requirement_document": requirement_document,
        "delivery_artifacts": delivery_artifacts,
        "execution_package": execution_package,
        "jira_payload": jira_payload,
        "jira_submission_result": jira_submission_result,
        "approval_status": approval_status,
        "interpreted_summary": interpreted_summary,
        "reasoning_summary": reasoning_summary,
        "next_step_guidance": _build_next_step_guidance(stage),
        "current_field": current_field,
        "current_field_label": current_field_label,
        "current_question": current_question,
        "current_question_reason": current_question_reason,
        "confidence_score": decision["confidence_score"],
        "clarification_feedback": clarification_feedback,
    }


def start_requirement_flow(user_input: str) -> Dict:
    session_id = create_session_id()
    requirement_state = initialize_requirement_state(user_input)
    decision = decide_next_step(requirement_state)

    initial_feedback = build_clarification_feedback(
        user_input=user_input,
        interpreted={"fields_to_update": {}, "should_override_single_field_write": False},
        next_field=decision["question_field"],
        next_question=decision["next_question"],
        current_question=None,
        current_question_reason=decision["reason"],
    )

    SESSION_STORE[session_id] = {
        "mode": "REQUIREMENT",
        "stage": "clarification",
        "requirement_state": requirement_state,
        "current_field": decision["question_field"],
        "requirement_document": None,
        "delivery_artifacts": None,
        "execution_package": None,
        "jira_payload": None,
        "jira_submission_result": None,
        "approval_status": "NOT_READY",
        "latest_ba_result": None,
    }

    ba_payload = build_ba_payload(
        stage="clarification",
        requirement_state=requirement_state,
        approval_status="NOT_READY",
        clarification_feedback=initial_feedback,
    )
    SESSION_STORE[session_id]["latest_ba_result"] = ba_payload

    return {
        "mode": "REQUIREMENT",
        "status": "CLARIFICATION_REQUIRED",
        "message": "I’ve started shaping this request into a structured requirement package.",
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def get_session(session_id: str) -> Optional[Dict]:
    return SESSION_STORE.get(session_id)


def apply_clarification_answer(requirement_state: Dict, field: str | None, user_input: str) -> Dict:
    if not field:
        return requirement_state

    updated_state = requirement_state.copy()
    updated_state[field] = user_input.strip()

    history = list(updated_state.get("conversation_history", []))
    history.append(
        {
            "role": "user",
            "content": user_input,
        }
    )
    updated_state["conversation_history"] = history

    return updated_state


def continue_requirement_flow(session_id: str, user_input: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    requirement_state = session["requirement_state"]
    approval_status = session.get("approval_status", "NOT_READY")

    # If this session was explicitly sent back for revision,
    # treat the next user input as revision feedback first.
    if approval_status == "REVISION_REQUESTED":
        revision_result = apply_revision_feedback(requirement_state, user_input)
        requirement_state = revision_result["updated_state"]
        session["requirement_state"] = requirement_state
        session["approval_status"] = "NOT_READY"
        session["stage"] = "clarification"
        session["requirement_document"] = None
        session["delivery_artifacts"] = None
        session["execution_package"] = None
        session["jira_payload"] = None
        session["jira_submission_result"] = None

        decision = decide_next_step(requirement_state)
        session["current_field"] = decision["question_field"]

        clarification_feedback = build_clarification_feedback(
            user_input=user_input,
            interpreted={"fields_to_update": {}, "should_override_single_field_write": False},
            next_field=decision["question_field"],
            next_question=decision["next_question"],
            current_question=decision["next_question"],
            current_question_reason=decision["reason"],
        )

        ba_payload = build_ba_payload(
            stage="clarification",
            requirement_state=requirement_state,
            approval_status="NOT_READY",
            clarification_feedback=clarification_feedback,
        )
        session["latest_ba_result"] = ba_payload

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": (
                "I interpreted your revision feedback and reopened the affected parts of the requirement."
            ),
            "session_id": session_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    current_field = session.get("current_field")
    trimmed_input = (user_input or "").strip()

    if current_field and is_weak_answer(trimmed_input):
        session["stage"] = "clarification"
        session["approval_status"] = "NOT_READY"

        latest_ba_result = session.get("latest_ba_result") or {}
        clarification_feedback = {
            "answer_status": "weak",
            "reflection_text": f"I still need a clearer answer for {current_field.replace('_', ' ')}.",
            "next_question": latest_ba_result.get("current_question"),
            "current_question": latest_ba_result.get("current_question"),
            "current_question_reason": latest_ba_result.get("current_question_reason"),
            "next_field": current_field,
        }

        ba_payload = build_ba_payload(
            stage="clarification",
            requirement_state=requirement_state,
            approval_status="NOT_READY",
            requirement_document=session.get("requirement_document"),
            delivery_artifacts=session.get("delivery_artifacts"),
            execution_package=session.get("execution_package"),
            jira_payload=session.get("jira_payload"),
            jira_submission_result=session.get("jira_submission_result"),
            clarification_feedback=clarification_feedback,
        )
        session["latest_ba_result"] = ba_payload

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": build_weak_answer_message(current_field),
            "session_id": session_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    latest_ba_result = session.get("latest_ba_result") or {}
    current_question = latest_ba_result.get("current_question")

    interpreted = interpret_clarification_answer(
        original_request=requirement_state.get("original_request", ""),
        current_question=current_question,
        current_field=current_field,
        user_input=trimmed_input,
    )

    if interpreted.get("should_override_single_field_write"):
        updated_state = requirement_state.copy()
        updates = interpreted.get("fields_to_update", {}) or {}

        for field, value in updates.items():
            updated_state[field] = value

        history = list(updated_state.get("conversation_history", []))
        history.append(
            {
                "role": "user",
                "content": trimmed_input,
            }
        )
        updated_state["conversation_history"] = history

        requirement_state = updated_state
    else:
        requirement_state = apply_clarification_answer(
            requirement_state=requirement_state,
            field=current_field,
            user_input=trimmed_input,
        )

    decision = decide_next_step(requirement_state)

    session["requirement_state"] = requirement_state
    session["current_field"] = decision["question_field"]

    if decision["next_action"] == "ASK":
        session["stage"] = "clarification"
        session["requirement_document"] = None
        session["delivery_artifacts"] = None
        session["execution_package"] = None
        session["jira_payload"] = None
        session["jira_submission_result"] = None
        session["approval_status"] = "NOT_READY"

        clarification_feedback = build_clarification_feedback(
            user_input=trimmed_input,
            interpreted=interpreted,
            next_field=decision["question_field"],
            next_question=decision["next_question"],
            current_question=current_question,
            current_question_reason=decision["reason"],
        )

        ba_payload = build_ba_payload(
            stage="clarification",
            requirement_state=requirement_state,
            approval_status="NOT_READY",
            clarification_feedback=clarification_feedback,
        )
        session["latest_ba_result"] = ba_payload

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": "I incorporated your last answer and I need one more detail before moving forward.",
            "session_id": session_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    requirement_document = generate_requirement_document(requirement_state)
    delivery_artifacts = generate_epic_and_stories(requirement_document)

    session["stage"] = "REVIEW_READY"
    session["requirement_document"] = requirement_document
    session["delivery_artifacts"] = delivery_artifacts
    session["execution_package"] = None
    session["jira_payload"] = None
    session["jira_submission_result"] = None
    session["approval_status"] = "PENDING_REVIEW"

    ba_payload = build_ba_payload(
        stage="review_ready",
        requirement_state=requirement_state,
        approval_status="PENDING_REVIEW",
        requirement_document=requirement_document,
        delivery_artifacts=delivery_artifacts,
    )
    session["latest_ba_result"] = ba_payload

    return {
        "mode": "REQUIREMENT",
        "status": "REVIEW_READY",
        "message": "I now have enough information to generate the requirement package for review.",
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def approve_requirement_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    if session.get("stage") != "REVIEW_READY":
        raise ValueError("Artifacts are not in a review-ready state.")

    session["stage"] = "EXECUTION_READY"
    session["approval_status"] = "APPROVED"

    ba_payload = build_ba_payload(
        stage="execution_ready",
        requirement_state=session["requirement_state"],
        approval_status="APPROVED",
        requirement_document=session["requirement_document"],
        delivery_artifacts=session["delivery_artifacts"],
        execution_package=session.get("execution_package"),
        jira_payload=session.get("jira_payload"),
        jira_submission_result=session.get("jira_submission_result"),
    )
    session["latest_ba_result"] = ba_payload

    return {
        "mode": "REQUIREMENT",
        "status": "EXECUTION_READY",
        "message": "Artifacts approved. The requirement package is now execution-ready.",
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def revise_requirement_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    session["stage"] = "clarification"
    session["approval_status"] = "REVISION_REQUESTED"

    ba_payload = build_ba_payload(
        stage="clarification",
        requirement_state=session["requirement_state"],
        approval_status="REVISION_REQUESTED",
        requirement_document=session.get("requirement_document"),
        delivery_artifacts=session.get("delivery_artifacts"),
        execution_package=session.get("execution_package"),
        jira_payload=session.get("jira_payload"),
        jira_submission_result=session.get("jira_submission_result"),
    )
    session["latest_ba_result"] = ba_payload

    return {
        "mode": "REQUIREMENT",
        "status": "REVISION_REQUIRED",
        "message": (
            "Revision requested. Tell me what should change, and I’ll reopen the affected parts of the requirement."
        ),
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def generate_jira_payload_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    if session.get("stage") != "EXECUTION_READY":
        raise ValueError("Artifacts must be approved before generating Jira payload.")

    requirement_document = session.get("requirement_document")
    delivery_artifacts = session.get("delivery_artifacts")
    if not requirement_document or not delivery_artifacts:
        raise ValueError("Missing requirement document or delivery artifacts.")

    execution_package = build_execution_package(requirement_document, delivery_artifacts)
    jira_payload = build_jira_payload(execution_package)

    session["execution_package"] = execution_package
    session["jira_payload"] = jira_payload
    session["stage"] = "JIRA_PAYLOAD_READY"

    ba_payload = build_ba_payload(
        stage="jira_payload_ready",
        requirement_state=session["requirement_state"],
        approval_status=session["approval_status"],
        requirement_document=requirement_document,
        delivery_artifacts=delivery_artifacts,
        execution_package=execution_package,
        jira_payload=jira_payload,
        jira_submission_result=session.get("jira_submission_result"),
    )
    session["latest_ba_result"] = ba_payload

    return {
        "mode": "EXECUTION",
        "status": "JIRA_PAYLOAD_READY",
        "message": "Jira payload generated successfully. Review it before sending.",
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def send_to_jira_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    jira_payload = session.get("jira_payload")
    if not jira_payload:
        raise ValueError("Generate Jira payload before sending to Jira.")

    submission_result = submit_jira_payload(jira_payload)

    session["jira_submission_result"] = submission_result
    session["stage"] = "JIRA_SUBMITTED"

    ba_payload = build_ba_payload(
        stage="jira_submitted",
        requirement_state=session["requirement_state"],
        approval_status=session["approval_status"],
        requirement_document=session["requirement_document"],
        delivery_artifacts=session["delivery_artifacts"],
        execution_package=session.get("execution_package"),
        jira_payload=session.get("jira_payload"),
        jira_submission_result=submission_result,
    )
    session["latest_ba_result"] = ba_payload

    return {
        "mode": "EXECUTION",
        "status": "JIRA_SUBMITTED",
        "message": "Jira issues created successfully.",
        "session_id": session_id,
        "question_result": None,
        "ba_result": ba_payload,
    }