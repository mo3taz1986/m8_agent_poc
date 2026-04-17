import base64
import json
import time
from pathlib import Path

import requests
import streamlit as st

def check_password():
    import os
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown("### Enter Access Code")
        password = st.text_input("Password", type="password")

        if password == os.getenv("APP_PASSWORD", "demo123"):
            st.session_state.authenticated = True
            st.rerun()
        elif password:
            st.error("Incorrect password")

        st.stop()


PROCESS_API_URL = "http://127.0.0.1:8000/process"
INGEST_API_URL = "http://127.0.0.1:8000/ingest"
HEALTH_API_URL = "http://127.0.0.1:8000/health"
APP_NAME = "M8 – AI Delivery Orchestrator"
APP_TAGLINE = "AI-driven requirement shaping and delivery orchestration."

STREAM_DELAY = 0.024
LOGO_PATH = Path("logo2.png")


def get_base64_image(image_path: Path) -> str:
    if not image_path.exists():
        return ""
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


def inject_custom_css() -> None:
    st.markdown(
        '''
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"], [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background-color: #ffffff;
        }

        section[data-testid="stSidebar"] {
            background-color: #e9e9ea;
            border-right: 1px solid #d7d7d9;
            width: 272px !important;
            min-width: 272px !important;
            max-width: 272px !important;
            transition: width 0.2s ease, min-width 0.2s ease, max-width 0.2s ease;
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 0.55rem;
            padding-bottom: 0.8rem;
            padding-left: 0.65rem;
            padding-right: 0.65rem;
        }

        section[data-testid="stSidebar"][aria-expanded="false"] {
            width: 4.4rem !important;
            min-width: 4.4rem !important;
            max-width: 4.4rem !important;
        }

        section[data-testid="stSidebar"][aria-expanded="false"] .block-container {
            padding-top: 0.5rem;
            padding-bottom: 0.6rem;
            padding-left: 0.35rem;
            padding-right: 0.35rem;
        }

        section[data-testid="stSidebar"][aria-expanded="false"] .m8-sidebar-expanded {
            display: none !important;
        }

        .m8-collapsed-icons {
            display: none;
        }

        section[data-testid="stSidebar"][aria-expanded="false"] .m8-collapsed-icons {
            display: flex !important;
            flex-direction: column;
            align-items: center;
            gap: 0.7rem;
            margin-top: 0.15rem;
        }

        .m8-collapsed-icon {
            width: 2.35rem;
            height: 2.35rem;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            color: #111111;
            background: transparent;
            border: 1px solid transparent;
            font-size: 1.05rem;
            line-height: 1;
        }

        .m8-collapsed-icon:hover {
            background: #f3f3f4;
            border-color: #d0d0d3;
        }

        .m8-main-topbar {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            padding-top: 0.15rem;
            padding-bottom: 0.5rem;
        }

        .m8-main-logo {
            width: 90px;
            height: auto;
            display: block;
        }

        .m8-sidebar-section-title {
            font-size: 0.69rem;
            font-weight: 600;
            color: #9DA0B1;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            margin: 0.1rem 0 0.45rem 0;
        }

        .m8-sidebar-helper {
            font-size: 0.7rem;
            color: #55555d;
            line-height: 1.45;
            margin-top: 0.1rem;
            margin-bottom: 0.55rem;
        }

        .m8-sidebar-divider {
            height: 1px;
            background: #d2d2d5;
            margin: 0.85rem 0;
        }

        .m8-sidebar-meta {
            display: flex;
            flex-direction: column;
            gap: 0.42rem;
        }

        .m8-sidebar-meta-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
        }

        .m8-sidebar-meta-label {
            font-size: 0.72rem;
            font-weight: 500;
            color: #111111;
            line-height: 1.35;
        }

        .m8-sidebar-meta-value {
            font-size: 0.72rem;
            color: #45454d;
            text-align: right;
            line-height: 1.35;
        }

        .m8-hero-wrap {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 34vh;
            text-align: center;
            padding-top: 1.5rem;
            padding-bottom: 1rem;
        }

        .m8-hero-title {
            font-size: 2.5rem;
            font-weight: 500;
            color: #222222;
            margin-bottom: 0.75rem;
            letter-spacing: -0.02em;
        }

        .m8-hero-subtitle {
            font-size: 0.95rem;
            color: #6b7280;
        }

        .m8-section-message {
            font-size: 0.98rem;
            color: #1f2937;
            line-height: 1.55;
        }

        .m8-reflection-block {
            font-size: 0.98rem;
            color: #1f2937;
            line-height: 1.6;
            margin-bottom: 0.65rem;
        }

        .m8-next-question {
            font-size: 0.98rem;
            color: #111111;
            line-height: 1.6;
            font-weight: 600;
        }

        .m8-stage-pill {
            display: inline-block;
            padding: 0.35rem 0.65rem;
            border-radius: 999px;
            background: #f3f4f6;
            color: #374151;
            font-size: 0.8rem;
            font-weight: 500;
            margin-bottom: 0.9rem;
        }

        [data-testid="stChatInput"] {
            border-top: none;
            background: transparent;
        }

        [data-testid="stChatInput"] > div {
            border-radius: 999px !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-secondaryFormSubmit"] {
            width: 100%;
            border-radius: 12px !important;
            border: 1px solid #c8c8cc !important;
            background: #f4f4f5 !important;
            color: #111111 !important;
            font-size: 0.72rem !important;
            font-weight: 500 !important;
            box-shadow: none !important;
            min-height: 2.15rem !important;
            transition: background 0.15s ease, border-color 0.15s ease !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
            background: #eeeeef !important;
            border-color: #b8b8bd !important;
            color: #111111 !important;
        }

        [data-testid="stExpander"] {
            border: none !important;
            background: transparent !important;
        }

        [data-testid="stExpander"] details {
            border: none !important;
            background: transparent !important;
        }

        [data-testid="stExpander"] summary {
            padding: 0.1rem 0 !important;
            color: #111111 !important;
            font-size: 0.74rem !important;
            font-weight: 500 !important;
        }

        [data-testid="stExpander"] summary:hover {
            background: transparent !important;
        }

        div[data-testid="stFileUploader"] {
            margin-top: 0.2rem;
        }

        div[data-testid="stFileUploader"] > section {
            padding: 0;
            border: none;
            background: transparent;
        }

        [data-testid="stFileUploaderDropzone"] {
            border: 1px dashed #c2c2c7 !important;
            border-radius: 14px !important;
            background: #f3f3f4 !important;
            padding: 0.8rem 0.8rem !important;
        }

        [data-testid="stFileUploaderDropzone"] div {
            font-family: 'Inter', sans-serif !important;
            font-size: 0.72rem !important;
            color: #111111 !important;
        }

        [data-testid="stFileUploaderDropzoneInstructions"] div,
        [data-testid="stFileUploaderDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzone"] small {
            font-size: 0.68rem !important;
            color: #5d5d65 !important;
            line-height: 1.4 !important;
        }

        [data-testid="stFileUploader"] button {
            font-size: 0.7rem !important;
            font-weight: 500 !important;
            padding: 0.28rem 0.68rem !important;
            border-radius: 10px !important;
        }

        .stCheckbox label {
            font-size: 0.71rem !important;
            font-weight: 500 !important;
            color: #111111 !important;
        }

        .stCheckbox {
            margin-top: -0.15rem;
            margin-bottom: -0.1rem;
        }

        .stCaption {
            font-size: 0.68rem !important;
            color: #5d5d65 !important;
        }
        </style>
        ''',
        unsafe_allow_html=True,
    )


def render_top_logo() -> None:
    logo_b64 = get_base64_image(LOGO_PATH)

    if logo_b64:
        st.markdown(
            f'''
            <div class="m8-main-topbar">
                <img class="m8-main-logo" src="data:image/png;base64,{logo_b64}" />
            </div>
            ''',
            unsafe_allow_html=True,
        )


def call_health_api() -> str:
    try:
        response = requests.get(HEALTH_API_URL, timeout=5)
        if response.status_code == 200:
            return "Connected"
        return f"Unavailable ({response.status_code})"
    except Exception:
        return "Offline"


def call_process_api(
    user_input: str = "",
    top_k: int = 4,
    session_id: str | None = None,
    action: str | None = None,
) -> dict:
    payload = {
        "input": user_input,
        "top_k": top_k,
        "session_id": session_id,
        "action": action,
    }

    try:
        response = requests.post(PROCESS_API_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "Could not connect to the backend API. "
                "Make sure FastAPI is running at http://127.0.0.1:8000"
            )
        }
    except requests.exceptions.Timeout:
        return {"error": "The backend API timed out while processing the request."}
    except requests.exceptions.HTTPError:
        return {
            "error": f"Backend returned an HTTP error: {response.status_code} - {response.text}"
        }
    except Exception as e:
        return {"error": f"Unexpected error while calling backend API: {str(e)}"}


def call_ingest_api(uploaded_file) -> dict:
    try:
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
        }

        response = requests.post(INGEST_API_URL, files=files, timeout=300)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        return {
            "error": (
                "Could not connect to the ingestion API. "
                "Make sure FastAPI is running at http://127.0.0.1:8000"
            )
        }
    except requests.exceptions.Timeout:
        return {"error": "The ingestion request timed out while processing the file."}
    except requests.exceptions.HTTPError:
        return {
            "error": f"Ingestion API returned an HTTP error: {response.status_code} - {response.text}"
        }
    except Exception as e:
        return {"error": f"Unexpected error while calling ingestion API: {str(e)}"}


def get_latest_status() -> str | None:
    if st.session_state.latest_ba_result:
        return st.session_state.latest_ba_result.get("status")
    return None


def stream_text_line(text: str, delay: float = STREAM_DELAY) -> None:
    placeholder = st.empty()
    rendered = ""

    for char in text:
        rendered += char
        placeholder.markdown(rendered)
        time.sleep(delay)

    placeholder.markdown(rendered)


def render_sources(sources: list[dict]) -> None:
    if not sources:
        st.info("No source chunks were returned.")
        return

    for idx, source in enumerate(sources, start=1):
        doc_name = source.get("doc_name", "unknown")
        section_title = source.get("section_title", "General")
        chunk_id = source.get("chunk_id", -1)
        hybrid_score = source.get("hybrid_score")
        rerank_score = source.get("rerank_score")
        text = source.get("text", "")

        title = f"Source {idx}: {doc_name} | {section_title} | chunk {chunk_id}"

        with st.expander(title):
            if hybrid_score is not None:
                try:
                    st.write(f"**Hybrid Score:** {float(hybrid_score):.4f}")
                except (TypeError, ValueError):
                    st.write(f"**Hybrid Score:** {hybrid_score}")

            if rerank_score is not None:
                try:
                    st.write(f"**Rerank Score:** {float(rerank_score):.4f}")
                except (TypeError, ValueError):
                    st.write(f"**Rerank Score:** {rerank_score}")

            st.write("**Text:**")
            st.write(text)


def render_question_result(
    question_result: dict,
    stream: bool = False,
    show_debug: bool = False,
) -> str:
    answer = question_result.get("answer", "")
    confidence = question_result.get("confidence", "unknown")
    grounding = question_result.get("grounding", {})
    grounding_score = grounding.get("score")
    grounding_verdict = grounding.get("verdict", "unknown")
    sources = question_result.get("sources", [])

    if stream:
        stream_text_line(answer)
    else:
        st.markdown(answer)

    if show_debug:
        st.markdown("### Response Details")
        st.write("**Mode:** QUESTION")
        st.write(f"**Confidence:** {confidence}")
        st.write(f"**Grounding Verdict:** {grounding_verdict}")

        if grounding_score is not None:
            try:
                st.write(f"**Grounding Score:** {float(grounding_score):.4f}")
            except (TypeError, ValueError):
                st.write(f"**Grounding Score:** {grounding_score}")

        st.markdown("### Retrieved Sources")
        render_sources(sources)

    return answer


def render_context_summary_in_chat(context_summary: dict) -> None:
    name          = context_summary.get("name", "Uploaded file")
    summary       = context_summary.get("summary", "")
    topics        = context_summary.get("topics", [])
    business_area = context_summary.get("business_area", "")
    signals       = context_summary.get("signals", [])
    potential_use = context_summary.get("potential_use", "")

    st.markdown(f"**Context Highlights — {name}**")
    st.markdown("---")
    if summary:
        st.markdown("**Summary**")
        st.markdown(summary)
    if topics:
        st.markdown("**Key Topics**")
        for t in topics:
            st.markdown(f"- {t}")
    if business_area:
        st.markdown(f"**Business Area:** {business_area}")
    if signals:
        st.markdown("**Signals Detected**")
        for s in signals:
            st.markdown(f"- {s}")
    if potential_use:
        st.markdown("**Potential Use**")
        st.markdown(potential_use)
    st.markdown("---")


def render_requirement_document(requirement_document: dict) -> None:
    pass  # replaced by render_final_summary


def render_delivery_artifacts(delivery_artifacts: dict) -> None:
    pass  # replaced by render_final_summary


def render_final_summary(requirement_document: dict, delivery_artifacts: dict) -> None:
    epic    = delivery_artifacts.get("epic", {}) if delivery_artifacts else {}
    stories = delivery_artifacts.get("stories", []) if delivery_artifacts else []

    epic_title    = epic.get("title", "")
    display_title = epic_title.replace("AI | Req | ", "").strip() if epic_title else ""

    st.markdown("## Requirement Summary")
    st.markdown("*Review the requirement below. This matches what will be sent to Jira.*")
    st.markdown("---")

    if display_title:
        st.markdown("### 🏷️ Epic Name")
        st.markdown(f"**{display_title}**")

    problem = requirement_document.get("problem_statement", "")
    if problem:
        st.markdown("### 📋 Request Summary")
        st.markdown(problem)

    objective = requirement_document.get("business_objective", "")
    if objective and objective != "Needs clarification":
        st.markdown("### 🎯 Objective")
        st.markdown(objective)

    scope = requirement_document.get("scope", "")
    if scope and scope != "Needs clarification":
        st.markdown("### 🔲 Scope")
        st.markdown(scope)

    stakeholders = requirement_document.get("stakeholders", "")
    if stakeholders and stakeholders != "Needs clarification":
        st.markdown("### 👥 Stakeholders")
        st.markdown(stakeholders)

    data_req = requirement_document.get("data_requirements", "")
    if data_req and data_req != "Needs clarification":
        st.markdown("### 🗄️ Data & Systems")
        st.markdown(data_req)

    frequency = requirement_document.get("frequency", "")
    if frequency and frequency != "Needs clarification":
        st.markdown("### 🔄 Frequency")
        st.markdown(frequency)

    success = requirement_document.get("success_criteria", "")
    if success and success != "Needs clarification":
        st.markdown("### ✅ Success Criteria")
        st.markdown(success)

    if stories:
        st.markdown("### 📝 Key Requirements")
        for idx, story in enumerate(stories, start=1):
            with st.expander(f"Story {idx}: {story.get('title', '')}"):
                st.markdown(f"**Description:** {story.get('description', '')}")
                ac = story.get("acceptance_criteria", [])
                if ac:
                    st.markdown("**Acceptance Criteria:**")
                    for item in ac:
                        st.markdown(f"- {item}")
                deps = story.get("dependencies", [])
                if deps:
                    st.markdown("**Dependencies:**")
                    for item in deps:
                        st.markdown(f"- {item}")
                risks = story.get("risks", [])
                if risks:
                    st.markdown("**Risks:**")
                    for item in risks:
                        st.markdown(f"- {item}")

    constraints = requirement_document.get("constraints", [])
    assumptions = requirement_document.get("assumptions", [])
    if constraints or assumptions:
        st.markdown("### ⚠️ Constraints & Assumptions")
        for item in constraints:
            st.markdown(f"- {item}")
        for item in assumptions:
            st.markdown(f"- {item}")

    risks = requirement_document.get("risks", [])
    if risks:
        st.markdown("### 🔴 Risks")
        for item in risks:
            st.markdown(f"- {item}")

    st.markdown("---")


def render_execution_package(execution_package: dict) -> None:
    st.markdown("### Execution Package")
    st.json(execution_package)


def render_jira_payload(jira_payload: dict) -> None:
    st.markdown("### Jira Payload Preview")

    epic = jira_payload.get("epic", {})
    stories = jira_payload.get("stories", [])

    st.markdown("#### Epic Payload")
    st.json(epic)

    st.markdown("#### Story Payloads")
    for idx, story in enumerate(stories, start=1):
        with st.expander(f"Jira Story Payload {idx}"):
            st.json(story)


def render_jira_submission_result(submission_result: dict) -> None:
    st.markdown("### Jira Submission Result")

    epic = submission_result.get("epic", {})
    stories = submission_result.get("stories", [])

    st.write(f"**Created Epic:** {epic.get('key', '')}")
    st.markdown("### Created Stories")
    for story in stories:
        st.write(f"- {story.get('key', '')}")


def shorten_summary_text(summary_text: str) -> str:
    if not summary_text:
        return ""

    replacements = {
        "I understand this as a request for a ": "Got it. This sounds like ",
        "I understand this as a request for an ": "Got it. This sounds like ",
        ". My goal is to turn it into a structured, execution-ready requirement package.": ".",
        "analytics or reporting capability": "a reporting need",
        "data pipeline or data movement capability": "a pipeline need",
        "workflow or process capability": "a workflow need",
        "analytical or modeling capability": "an analytics need",
        "business capability": "a business need",
    }

    text = summary_text
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.strip()


def build_clarification_response_text(message: str, ba_result: dict | None) -> str:
    if not ba_result:
        return message.strip()

    feedback = (ba_result or {}).get("clarification_feedback") or {}
    reflection_text = (feedback.get("reflection_text") or "").strip()
    next_question = (feedback.get("next_question") or "").strip()

    if reflection_text and next_question:
        return reflection_text + "\n\n" + next_question

    if reflection_text:
        return reflection_text

    requirement_state = ba_result.get("requirement_state", {})
    conversation_history = requirement_state.get("conversation_history", [])
    summary_text = (ba_result.get("interpreted_summary") or {}).get("summary_text", "")
    current_question = ba_result.get("current_question", "")
    revision_summary = ba_result.get("revision_summary", "")

    show_summary = len(conversation_history) <= 1
    show_revision_bridge = bool(revision_summary)

    generic_messages = {
        "I incorporated your last answer and I need one more detail before moving forward.",
        "I’ve started shaping this request into a structured requirement package.",
    }

    parts = []
    clean_message = (message or "").strip()

    if show_revision_bridge:
        parts.append("Understood. Let’s adjust that.")
    elif clean_message and clean_message not in generic_messages:
        parts.append(clean_message)
    else:
        if show_summary and summary_text:
            parts.append(shorten_summary_text(summary_text))

        if current_question:
            parts.append(current_question)
        elif clean_message:
            parts.append(clean_message)

    return "\n\n".join(part for part in parts if part).strip()


def render_clarification_response(
    message: str,
    ba_result: dict | None,
    stream: bool = False,
) -> str:
    feedback = (ba_result or {}).get("clarification_feedback") or {}
    reflection_text = (feedback.get("reflection_text") or "").strip()
    next_question = (feedback.get("next_question") or "").strip()

    if reflection_text or next_question:
        response_text = "\n\n".join(part for part in [reflection_text, next_question] if part)

        if stream:
            stream_text_line(response_text)
        else:
            if reflection_text:
                st.markdown(f"<div class='m8-reflection-block'>{reflection_text}</div>", unsafe_allow_html=True)
            if next_question:
                st.markdown(f"<div class='m8-next-question'>{next_question}</div>", unsafe_allow_html=True)

        return response_text

    response_text = build_clarification_response_text(message, ba_result)

    if stream:
        stream_text_line(response_text)
    else:
        st.markdown(f"<div class='m8-section-message'>{response_text}</div>", unsafe_allow_html=True)

    return response_text


def render_non_clarification_ba_result(
    mode: str,
    status: str,
    message: str,
    ba_result: dict | None,
    session_id: str | None,
    stream: bool = False,
) -> str:
    stage_text = f"Stage: {status.replace('_', ' ').title()}"
    st.markdown(f"<div class='m8-stage-pill'>{stage_text}</div>", unsafe_allow_html=True)

    if stream:
        stream_text_line(message)
    else:
        st.markdown(f"<div class='m8-section-message'>{message}</div>", unsafe_allow_html=True)

    if ba_result:
        approval_status = ba_result.get("approval_status", "UNKNOWN")
        requirement_document = ba_result.get("requirement_document")
        delivery_artifacts = ba_result.get("delivery_artifacts")
        execution_package = ba_result.get("execution_package")
        jira_payload = ba_result.get("jira_payload")
        jira_submission_result = ba_result.get("jira_submission_result")

        st.write(f"**Approval Status:** {approval_status}")

        if requirement_document:
            render_final_summary(requirement_document, delivery_artifacts)

        if execution_package:
            render_execution_package(execution_package)

        if jira_payload:
            render_jira_payload(jira_payload)

        if jira_submission_result:
            render_jira_submission_result(jira_submission_result)

    return f"{mode}: {message}"


def render_ba_result(
    mode: str,
    status: str,
    message: str,
    ba_result: dict | None,
    session_id: str | None,
    stream: bool = False,
) -> str:
    clarification_statuses = {"CLARIFICATION_REQUIRED", "REVISION_REQUIRED"}
    stage = (ba_result or {}).get("stage")

    if status in clarification_statuses or stage == "clarification":
        return render_clarification_response(
            message=message,
            ba_result=ba_result,
            stream=stream,
        )

    return render_non_clarification_ba_result(
        mode=mode,
        status=status,
        message=message,
        ba_result=ba_result,
        session_id=session_id,
        stream=stream,
    )


def build_upload_context_prompt() -> str:
    return (
        "Before I move to the next step, would you like to upload a text or PDF file as business context?\n\n"
        "This can help accelerate delivery by giving the product team more background, improving knowledge sharing, "
        "and reducing back and forth during execution.\n\n"
        "Reply yes to upload context or no to continue without it."
    )


def build_upload_complete_prompt() -> str:
    return (
        "Please upload the file from the Upload context area in the sidebar. "
        "Once the upload is finished, type complete and I will move to the next step."
    )


def should_prompt_for_context(status: str) -> bool:
    return status in {"REVIEW_READY", "DELIVERY_ARTIFACTS_READY"}


def handle_context_gate_response(user_input: str) -> tuple[bool, str | None]:
    normalized = (user_input or "").strip().lower()

    if st.session_state.get("awaiting_context_confirmation"):
        if normalized in {"yes", "y", "confirm", "continue", "ok", "proceed"}:
            st.session_state.awaiting_context_confirmation = False
            st.session_state.context_summary_pending = None
            st.session_state.context_gate_completed = True
            return True, "Context confirmed. Proceeding to review."
        if normalized in {"no", "n", "skip"}:
            st.session_state.awaiting_context_confirmation = False
            st.session_state.context_summary_pending = None
            st.session_state.context_gate_completed = True
            return True, "Understood. Continuing without this context."
        return True, "Reply **yes** to confirm this context or **no** to skip."

    return False, None


def handle_action(action: str, top_k: int) -> None:
    result = call_process_api(
        user_input="",
        top_k=top_k,
        session_id=st.session_state.ba_session_id,
        action=action,
    )

    if "error" in result:
        st.error(result["error"])
        return

    mode = result.get("mode", "REQUIREMENT")
    status = result.get("status", "UNKNOWN")
    message = result.get("message", "")
    ba_result = result.get("ba_result")
    returned_session_id = result.get("session_id")

    if returned_session_id:
        st.session_state.ba_session_id = returned_session_id

    st.session_state.latest_ba_result = result

    with st.chat_message("assistant"):
        assistant_text = render_ba_result(
            mode=mode,
            status=status,
            message=message,
            ba_result=ba_result,
            session_id=returned_session_id or st.session_state.ba_session_id,
            stream=True,
        )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
        }
    )

    st.rerun()


st.set_page_config(
    page_title=APP_NAME,
    page_icon="💬",
    layout="wide",
)

inject_custom_css()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "ba_session_id" not in st.session_state:
    st.session_state.ba_session_id = None

if "latest_ba_result" not in st.session_state:
    st.session_state.latest_ba_result = None

if "awaiting_context_offer" not in st.session_state:
    st.session_state.awaiting_context_offer = False

if "awaiting_context_complete" not in st.session_state:
    st.session_state.awaiting_context_complete = False

if "context_gate_completed" not in st.session_state:
    st.session_state.context_gate_completed = False

if "context_summary_pending" not in st.session_state:
    st.session_state.context_summary_pending = None

if "awaiting_context_confirmation" not in st.session_state:
    st.session_state.awaiting_context_confirmation = False

render_top_logo()

with st.sidebar:
    st.markdown(
        '''
        <div class="m8-collapsed-icons">
            <div class="m8-collapsed-icon">✎</div>
            <div class="m8-collapsed-icon">⌕</div>
            <div class="m8-collapsed-icon">⤴</div>
            <div class="m8-collapsed-icon">☰</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    st.markdown("<div class='m8-sidebar-expanded'>", unsafe_allow_html=True)

    latest_status = get_latest_status()
    session_id = st.session_state.ba_session_id
    api_status = call_health_api()

    st.markdown("<div class='m8-sidebar-section-title'>Workspace</div>", unsafe_allow_html=True)

    with st.expander("Upload context", expanded=False, icon=":material/attach_file:"):
        st.markdown(
            "<div class='m8-sidebar-helper'>Add business context to ground the conversation.</div>",
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload a .pdf or .txt file",
            type=["pdf", "txt"],
            accept_multiple_files=False,
            label_visibility="collapsed",
        )

        if uploaded_file is not None:
            st.caption(f"Selected: {uploaded_file.name}")

            if st.button("Add file", icon=":material/upload_file:", use_container_width=True):
                with st.spinner("Uploading and rebuilding indexes..."):
                    ingest_result = call_ingest_api(uploaded_file)

                if "error" in ingest_result:
                    st.error(ingest_result["error"])
                else:
                    st.success("Context added successfully.")

    st.markdown("<div class='m8-sidebar-divider'></div>", unsafe_allow_html=True)

    st.markdown("<div class='m8-sidebar-section-title'>System</div>", unsafe_allow_html=True)
    st.markdown(
        f'''
        <div class="m8-sidebar-meta">
            <div class="m8-sidebar-meta-row">
                <div class="m8-sidebar-meta-label">Session</div>
                <div class="m8-sidebar-meta-value">{session_id or "None"}</div>
            </div>
            <div class="m8-sidebar-meta-row">
                <div class="m8-sidebar-meta-label">Status</div>
                <div class="m8-sidebar-meta-value">{latest_status or "Ready"}</div>
            </div>
            <div class="m8-sidebar-meta-row">
                <div class="m8-sidebar-meta-label">API</div>
                <div class="m8-sidebar-meta-value">{api_status}</div>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    st.markdown("<div class='m8-sidebar-divider'></div>", unsafe_allow_html=True)

    st.markdown("<div class='m8-sidebar-section-title'>Preferences</div>", unsafe_allow_html=True)
    show_debug = st.checkbox("Show AI reasoning", value=False)

    st.markdown("<div class='m8-sidebar-divider'></div>", unsafe_allow_html=True)

    if st.button("Reset session", icon=":material/restart_alt:", use_container_width=True):
        st.session_state.ba_session_id = None
        st.session_state.latest_ba_result = None
        st.session_state.awaiting_context_offer = False
        st.session_state.awaiting_context_complete = False
        st.session_state.context_gate_completed = False
        st.session_state.context_summary_pending = None
        st.session_state.awaiting_context_confirmation = False
        st.success("Session reset.")

    st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown(
        '''
        <div class="m8-hero-wrap">
            <div class="m8-hero-title">How can I help you today</div>
            <div class="m8-hero-subtitle">Bring a request, upload context, and I’ll help shape it into something actionable.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

if st.session_state.get("awaiting_context_confirmation") and st.session_state.get("context_summary_pending"):
    with st.chat_message("assistant"):
        render_context_summary_in_chat(st.session_state.context_summary_pending)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

latest_status = get_latest_status()

# ── Upload gate — shown at REVIEW_READY before the Approve/Revise step ──
# Positioned in the main screen (not the sidebar) so the user decides here
# whether to upload business context before reviewing, or skip it.
if (
    st.session_state.ba_session_id
    and latest_status in {"REVIEW_READY", "DELIVERY_ARTIFACTS_READY"}
    and not st.session_state.context_gate_completed
    and not st.session_state.awaiting_context_confirmation
):
    st.markdown("## Upload Business Context")
    st.markdown(
        "Optionally upload a .pdf or .txt file with business context "
        "to ground the requirement shaping, or click Next Step to proceed."
    )

    uploaded_file_inline = st.file_uploader(
        "Upload a .pdf or .txt file",
        type=["pdf", "txt"],
        accept_multiple_files=False,
        label_visibility="collapsed",
        key="inline_upload",
    )

    col_upload, col_skip = st.columns(2)

    with col_upload:
        upload_clicked = st.button(
            "Upload & Summarise",
            icon=":material/upload_file:",
            use_container_width=True,
            disabled=uploaded_file_inline is None,
            key="inline_upload_btn",
        )

    with col_skip:
        skip_clicked = st.button(
            "Next Step",
            icon=":material/arrow_forward:",
            use_container_width=True,
            key="inline_skip_btn",
        )

    if upload_clicked and uploaded_file_inline is not None:
        with st.spinner("Uploading and analysing context..."):
            ingest_result = call_ingest_api(uploaded_file_inline)
        if "error" in ingest_result:
            st.error(ingest_result["error"])
        else:
            context_summary = ingest_result.get("context_summary")
            if context_summary:
                st.session_state.context_summary_pending = context_summary
                st.session_state.awaiting_context_confirmation = True
                st.session_state.context_gate_completed = False
            else:
                st.session_state.context_gate_completed = True
            st.rerun()

    if skip_clicked:
        st.session_state.context_gate_completed = True
        st.session_state.context_summary_pending = None
        st.session_state.awaiting_context_confirmation = False
        st.rerun()

# ── Review Actions — shown after context gate resolved ──
if (
    st.session_state.ba_session_id
    and latest_status in {"REVIEW_READY", "DELIVERY_ARTIFACTS_READY"}
    and st.session_state.context_gate_completed
):
    st.markdown("## Review Actions")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Approve"):
            # One-click: approve AND generate Jira payload in the background
            with st.spinner("Approving and generating Jira payload..."):
                handle_action(action="APPROVE", top_k=4)
                handle_action(action="GENERATE_JIRA", top_k=4)

    with col2:
        if st.button("Revise"):
            handle_action(action="REVISE", top_k=4)

if st.session_state.ba_session_id and latest_status == "EXECUTION_READY":
    # Jira payload is generated automatically on Approve — fallback only
    if not st.session_state.latest_ba_result or not (
        st.session_state.latest_ba_result.get("ba_result") or {}
    ).get("jira_payload"):
        st.markdown("## Execution")
        if st.button("Generate Jira Payload"):
            handle_action(action="GENERATE_JIRA", top_k=4)

if st.session_state.ba_session_id and latest_status == "JIRA_PAYLOAD_READY":
    st.markdown("## Jira Submission")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Send to Jira"):
            handle_action(action="SEND_TO_JIRA", top_k=4)

    with col2:
        jira_payload = None
        if st.session_state.latest_ba_result:
            ba_result = st.session_state.latest_ba_result.get("ba_result", {})
            jira_payload = ba_result.get("jira_payload")

        if jira_payload:
            st.download_button(
                label="Download Jira Payload JSON",
                data=json.dumps(jira_payload, indent=2),
                file_name="jira_payload.json",
                mime="application/json",
            )

user_input = st.chat_input("Ask anything")

if user_input:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    should_rerun = False

    with st.chat_message("assistant"):
        handled_gate, gate_response = handle_context_gate_response(user_input)

        if handled_gate:
            assistant_text = gate_response or ""
            stream_text_line(assistant_text)
            should_rerun = st.session_state.context_gate_completed
        else:
            with st.spinner("Processing..."):
                result = call_process_api(
                    user_input=user_input,
                    top_k=4,
                    session_id=st.session_state.ba_session_id,
                )

            if "error" in result:
                st.error(result["error"])
                assistant_text = f"Error: {result['error']}"
            else:
                mode = result.get("mode", "UNKNOWN")
                status = result.get("status", "UNKNOWN")
                message = result.get("message", "")
                returned_session_id = result.get("session_id")
                question_result = result.get("question_result")
                ba_result = result.get("ba_result")

                # Only persist a session ID for REQUIREMENT / EXECUTION flows.
                # When mode is QUESTION — including after an ambiguity clarification
                # resolves to "understand the topic" — the returned session_id belongs
                # to the now-consumed pending intent and must not be kept. If kept, the
                # next unrelated message gets routed through continue_requirement_flow
                # with a stale session, causing the previous question's context to bleed
                # into the next turn (carry-over bug).
                if returned_session_id and mode in {"REQUIREMENT", "EXECUTION"}:
                    st.session_state.ba_session_id = returned_session_id
                elif mode == "QUESTION":
                    # Clear any stale pending-intent session so next input starts fresh
                    st.session_state.ba_session_id = None

                if mode in {"REQUIREMENT", "EXECUTION"}:
                    st.session_state.latest_ba_result = result

                    if False:  # context offer now handled by in-screen upload gate
                        pass
                    else:
                        if status in {
                            "REVIEW_READY",
                            "DELIVERY_ARTIFACTS_READY",
                            "REVISION_REQUIRED",
                            "EXECUTION_READY",
                            "JIRA_PAYLOAD_READY",
                            "JIRA_SUBMITTED",
                        }:
                            should_rerun = True

                        if mode == "QUESTION" and question_result:
                            assistant_text = render_question_result(
                                question_result,
                                stream=True,
                                show_debug=show_debug,
                            )
                        else:
                            assistant_text = render_ba_result(
                                mode=mode,
                                status=status,
                                message=message,
                                ba_result=ba_result,
                                session_id=returned_session_id or st.session_state.ba_session_id,
                                stream=True,
                            )

                else:
                    if mode == "QUESTION" and question_result:
                        assistant_text = render_question_result(
                            question_result,
                            stream=True,
                            show_debug=show_debug,
                        )
                    else:
                        assistant_text = render_ba_result(
                            mode=mode,
                            status=status,
                            message=message,
                            ba_result=ba_result,
                            session_id=returned_session_id or st.session_state.ba_session_id,
                            stream=True,
                        )



    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_text,
        }
    )

    if should_rerun:
        st.rerun()
