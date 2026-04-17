from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.config import REDIS_URL, SESSION_TTL_SECONDS
from src.services.session_store import SessionStore
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

# ── Session store ─────────────────────────────────────────────────────────────
# Single module-level instance shared across all requests.
# Uses Redis when REDIS_URL is set in .env, falls back to in-memory dict
# automatically when REDIS_URL is empty or Redis is unreachable.
session_store = SessionStore(redis_url=REDIS_URL, ttl_seconds=SESSION_TTL_SECONDS)


# ── Canonical stage names ─────────────────────────────────────────────────────
# All stage values stored in session dicts and the requests index use lowercase.
# Format for display at render time — never store uppercase stage strings.
#
#   clarification
#   review_ready
#   delivery_artifacts_ready
#   execution_ready
#   jira_payload_ready
#   jira_submitted


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def create_session_id() -> str:
    return session_store.create_session_id()


def _build_next_step_guidance(stage: str) -> str:
    if stage == "clarification":
        return "Answer the current question and I will refine the requirement further."
    if stage == "review_ready":
        return "Review the generated requirement package and decide whether to approve it or request revision."
    if stage == "delivery_artifacts_ready":
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

    review_stages = {"review_ready", "delivery_artifacts_ready", "execution_ready", "jira_payload_ready", "jira_submitted"}

    if stage in review_stages:
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


def _derive_initial_title(shape_result: Optional[Dict]) -> str:
    """
    Derive a working title for a new request.

    Priority:
      1. shape_result["resolved_label"]  — specific and immediate
      2. "Draft Request"                  — safe fallback

    The title is later promoted to the epic name once artifacts are generated.
    See _promote_title_from_epic().
    """
    if shape_result:
        label = shape_result.get("resolved_label") or shape_result.get("resolved_category")
        if label:
            return str(label).strip()
    return "Draft Request"


def _promote_title_from_epic(request_id: str, delivery_artifacts: Optional[Dict]) -> None:
    """
    Once delivery artifacts are generated, upgrade the request title to the
    epic name so the sidebar shows a meaningful label.

    Strips the 'AI | Req | ' prefix that the backend stores in epic titles
    because that prefix is Jira formatting — not a human-readable title.
    """
    if not request_id or not delivery_artifacts:
        return

    epic_title = (delivery_artifacts.get("epic") or {}).get("title", "")
    if not epic_title:
        return

    for prefix in ("AI | Req | ", "AI | req | ", "AI|Req|", "AI|req|"):
        if epic_title.startswith(prefix):
            epic_title = epic_title[len(prefix):].strip()
            break

    if epic_title:
        session_store.update_request_metadata(
            request_id,
            title=epic_title,
            last_updated=_now_iso(),
        )


def _sync_messages_to_index(request_id: str, messages: List[Dict]) -> None:
    """
    Persist the rendered chat messages list to the request record in the index.
    Only stores role + content — debug payloads are intentionally excluded.
    """
    if not request_id:
        return

    clean = [
        {"role": m["role"], "content": m.get("content", "")}
        for m in messages
        if m.get("role") in {"user", "assistant"}
    ]

    session_store.update_request_metadata(
        request_id,
        messages=clean,
        last_updated=_now_iso(),
    )


def start_requirement_flow(
    user_input: str,
    shape_result: Optional[Dict] = None,
    metadata_result: Optional[Dict] = None,
) -> Dict:
    """
    Start a new BA requirement session.

    shape_result — optional shape dict from the Meaning Agent.
    metadata_result — optional result from the Metadata Agent.

    Creates both a session record and a request record in the index.
    """
    session_id = create_session_id()
    request_id = session_store.create_request_id()
    requirement_state = initialize_requirement_state(user_input)

    if shape_result:
        requirement_state["_shape_result"] = shape_result
        resolved_category = shape_result.get("resolved_category")
        if resolved_category:
            requirement_state["_resolved_request_type"] = resolved_category

    if metadata_result:
        requirement_state["_metadata_result"] = metadata_result

    decision = decide_next_step(requirement_state)

    # Build opening message before calling build_clarification_feedback
    if shape_result and shape_result.get("resolved_label"):
        label = shape_result["resolved_label"]
        message = f"I've identified this as a {label}. Let me shape it into a structured requirement."
    else:
        message = "I've started shaping this request into a structured requirement package."

    if metadata_result and not metadata_result.get("skipped"):
        rec = metadata_result.get("recommendation")
        top = metadata_result.get("top_match")
        if rec == "REUSE" and top:
            message += (
                f" Note: a closely matching asset already exists — "
                f"\"{top['name']}\" (owned by {top['owner']}). "
                f"You may want to review it before we proceed."
            )
        elif rec == "EXTEND" and top:
            message += (
                f" Note: a related asset may be extendable — "
                f"\"{top['name']}\" (owned by {top['owner']}). "
                f"We can proceed, but it's worth checking if an extension covers this."
            )

    initial_feedback = build_clarification_feedback(
        user_input=user_input,
        interpreted={"fields_to_update": {}, "should_override_single_field_write": False},
        next_field=decision["question_field"],
        next_question=decision["next_question"],
        current_question=None,
        current_question_reason=decision["reason"],
        opening_message=message,
    )

    new_session = {
        "mode": "REQUIREMENT",
        "stage": "clarification",          # lowercase — canonical
        "request_id": request_id,
        "requirement_state": requirement_state,
        "current_field": decision["question_field"],
        "shape_result": shape_result,
        "metadata_result": metadata_result,
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
    new_session["latest_ba_result"] = ba_payload

    # Persist session
    session_store.set(session_id, new_session)

    # Register request in the index
    initial_title = _derive_initial_title(shape_result)
    session_store.add_request_to_index(
        request_id=request_id,
        session_id=session_id,
        title=initial_title,
        status="clarification",
        last_updated=_now_iso(),
    )

    return {
        "mode": "REQUIREMENT",
        "status": "CLARIFICATION_REQUIRED",
        "message": message,
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def get_session(session_id: str) -> Optional[Dict]:
    return session_store.get(session_id)


def apply_clarification_answer(requirement_state: Dict, field: str | None, user_input: str) -> Dict:
    if not field:
        return requirement_state

    updated_state = requirement_state.copy()
    updated_state[field] = user_input.strip()

    history = list(updated_state.get("conversation_history", []))
    history.append({"role": "user", "content": user_input})
    updated_state["conversation_history"] = history

    return updated_state


def continue_requirement_flow(session_id: str, user_input: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    request_id = session.get("request_id", "")
    requirement_state = session["requirement_state"]
    approval_status = session.get("approval_status", "NOT_READY")

    # Revision path
    if approval_status == "REVISION_REQUESTED":
        revision_result = apply_revision_feedback(requirement_state, user_input)
        requirement_state = revision_result["updated_state"]

        decision = decide_next_step(requirement_state)

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

        session["requirement_state"] = requirement_state
        session["approval_status"] = "NOT_READY"
        session["stage"] = "clarification"
        session["requirement_document"] = None
        session["delivery_artifacts"] = None
        session["execution_package"] = None
        session["jira_payload"] = None
        session["jira_submission_result"] = None
        session["current_field"] = decision["question_field"]
        session["latest_ba_result"] = ba_payload
        session_store.set(session_id, session)

        session_store.update_request_metadata(
            request_id,
            status="clarification",
            last_updated=_now_iso(),
        )

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": "I interpreted your revision feedback and reopened the affected parts of the requirement.",
            "session_id": session_id,
            "request_id": request_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    current_field = session.get("current_field")
    trimmed_input = (user_input or "").strip()

    # Weak answer — re-ask the same question
    if current_field and is_weak_answer(trimmed_input):
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

        session["stage"] = "clarification"
        session["approval_status"] = "NOT_READY"
        session["latest_ba_result"] = ba_payload
        session_store.set(session_id, session)

        session_store.update_request_metadata(
            request_id,
            status="clarification",
            last_updated=_now_iso(),
        )

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": build_weak_answer_message(current_field),
            "session_id": session_id,
            "request_id": request_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    # Normal clarification answer
    latest_ba_result = session.get("latest_ba_result") or {}
    current_question = latest_ba_result.get("current_question")

    interpreted = interpret_clarification_answer(
        original_request=requirement_state.get("original_request", ""),
        current_question=current_question,
        current_field=current_field,
        user_input=trimmed_input,
        requirement_state=requirement_state,
    )

    if interpreted.get("should_override_single_field_write"):
        updated_state = requirement_state.copy()
        updates = interpreted.get("fields_to_update", {}) or {}

        for field, value in updates.items():
            if updated_state.get(field) is None or field == current_field:
                updated_state[field] = value

        # Always guarantee the current field is written
        if current_field and updated_state.get(current_field) is None:
            updated_state[current_field] = trimmed_input

        history = list(updated_state.get("conversation_history", []))
        history.append({"role": "user", "content": trimmed_input})
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

        session["stage"] = "clarification"
        session["requirement_document"] = None
        session["delivery_artifacts"] = None
        session["execution_package"] = None
        session["jira_payload"] = None
        session["jira_submission_result"] = None
        session["approval_status"] = "NOT_READY"
        session["latest_ba_result"] = ba_payload
        session_store.set(session_id, session)

        session_store.update_request_metadata(
            request_id,
            status="clarification",
            last_updated=_now_iso(),
        )

        return {
            "mode": "REQUIREMENT",
            "status": "CLARIFICATION_REQUIRED",
            "message": "I incorporated your last answer and I need one more detail before moving forward.",
            "session_id": session_id,
            "request_id": request_id,
            "question_result": None,
            "ba_result": ba_payload,
        }

    # All fields complete — generate artifacts
    requirement_document = generate_requirement_document(requirement_state)
    delivery_artifacts = generate_epic_and_stories(requirement_document)

    ba_payload = build_ba_payload(
        stage="review_ready",
        requirement_state=requirement_state,
        approval_status="PENDING_REVIEW",
        requirement_document=requirement_document,
        delivery_artifacts=delivery_artifacts,
    )

    session["stage"] = "review_ready"
    session["requirement_document"] = requirement_document
    session["delivery_artifacts"] = delivery_artifacts
    session["execution_package"] = None
    session["jira_payload"] = None
    session["jira_submission_result"] = None
    session["approval_status"] = "PENDING_REVIEW"
    session["latest_ba_result"] = ba_payload
    session_store.set(session_id, session)

    # Promote title to epic name now that artifacts exist
    _promote_title_from_epic(request_id, delivery_artifacts)

    session_store.update_request_metadata(
        request_id,
        status="review_ready",
        last_updated=_now_iso(),
    )

    return {
        "mode": "REQUIREMENT",
        "status": "REVIEW_READY",
        "message": "I now have enough information to generate the requirement package for review.",
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def approve_requirement_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    if session.get("stage") != "review_ready":
        raise ValueError("Artifacts are not in a review-ready state.")

    request_id = session.get("request_id", "")

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

    session["stage"] = "execution_ready"
    session["approval_status"] = "APPROVED"
    session["latest_ba_result"] = ba_payload
    session_store.set(session_id, session)

    session_store.update_request_metadata(
        request_id,
        status="execution_ready",
        last_updated=_now_iso(),
    )

    return {
        "mode": "REQUIREMENT",
        "status": "EXECUTION_READY",
        "message": "Artifacts approved. The requirement package is now execution-ready.",
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def revise_requirement_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    request_id = session.get("request_id", "")

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

    session["stage"] = "clarification"
    session["approval_status"] = "REVISION_REQUESTED"
    session["latest_ba_result"] = ba_payload
    session_store.set(session_id, session)

    session_store.update_request_metadata(
        request_id,
        status="clarification",
        last_updated=_now_iso(),
    )

    return {
        "mode": "REQUIREMENT",
        "status": "REVISION_REQUIRED",
        "message": "Revision requested. Tell me what should change, and I'll reopen the affected parts of the requirement.",
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def generate_jira_payload_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    if session.get("stage") != "execution_ready":
        raise ValueError("Artifacts must be approved before generating Jira payload.")

    request_id = session.get("request_id", "")
    requirement_document = session.get("requirement_document")
    delivery_artifacts = session.get("delivery_artifacts")
    if not requirement_document or not delivery_artifacts:
        raise ValueError("Missing requirement document or delivery artifacts.")

    execution_package = build_execution_package(requirement_document, delivery_artifacts)
    jira_payload = build_jira_payload(execution_package)

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

    session["execution_package"] = execution_package
    session["jira_payload"] = jira_payload
    session["stage"] = "jira_payload_ready"
    session["latest_ba_result"] = ba_payload
    session_store.set(session_id, session)

    session_store.update_request_metadata(
        request_id,
        status="jira_payload_ready",
        last_updated=_now_iso(),
    )

    return {
        "mode": "EXECUTION",
        "status": "JIRA_PAYLOAD_READY",
        "message": "Jira payload generated successfully. Review it before sending.",
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


def send_to_jira_flow(session_id: str) -> Dict:
    session = get_session(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    request_id = session.get("request_id", "")
    jira_payload = session.get("jira_payload")
    if not jira_payload:
        raise ValueError("Generate Jira payload before sending to Jira.")

    submission_result = submit_jira_payload(jira_payload)

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

    session["jira_submission_result"] = submission_result
    session["stage"] = "jira_submitted"
    session["latest_ba_result"] = ba_payload
    session_store.set(session_id, session)

    session_store.update_request_metadata(
        request_id,
        status="jira_submitted",
        last_updated=_now_iso(),
    )

    return {
        "mode": "EXECUTION",
        "status": "JIRA_SUBMITTED",
        "message": "Jira issues created successfully.",
        "session_id": session_id,
        "request_id": request_id,
        "question_result": None,
        "ba_result": ba_payload,
    }


# ── Message persistence helpers ───────────────────────────────────────────────
# Called from app.py after every assistant turn to keep the index in sync
# with the rendered chat thread.

def persist_messages_for_session(session_id: str, messages: List[Dict]) -> None:
    """
    Sync the rendered messages list to the request record in the index.
    Looks up request_id from session_id via a reverse index scan.

    Call this from app.py after appending each assistant message:
      ba_service.persist_messages_for_session(
          st.session_state.ba_session_id,
          st.session_state.messages,
      )
    """
    record = session_store.get_request_by_session_id(session_id)
    if not record:
        return

    _sync_messages_to_index(record["request_id"], messages)
