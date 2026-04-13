import base64
from typing import Dict, List, Any

import requests

from src.config import (
    JIRA_BASE_URL,
    JIRA_EMAIL,
    JIRA_API_TOKEN,
    JIRA_PROJECT_KEY,
    JIRA_EPIC_ISSUE_TYPE,
    JIRA_STORY_ISSUE_TYPE,
)


def jira_is_configured() -> bool:
    return all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY])


def build_jira_auth_header() -> Dict[str, str]:
    token = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode("utf-8")).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def adf_paragraph(text: str) -> Dict[str, Any]:
    return {
        "type": "paragraph",
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }


def adf_bullet_list(items: List[str]) -> Dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": item,
                            }
                        ],
                    }
                ],
            }
            for item in items
        ],
    }


def text_to_adf_document(paragraphs: List[str], bullet_sections: Dict[str, List[str]] | None = None) -> Dict[str, Any]:
    content = []

    for paragraph in paragraphs:
        if paragraph and paragraph.strip():
            content.append(adf_paragraph(paragraph.strip()))

    if bullet_sections:
        for heading, items in bullet_sections.items():
            if heading and heading.strip():
                content.append(adf_paragraph(heading.strip()))
            if items:
                content.append(adf_bullet_list(items))

    return {
        "version": 1,
        "type": "doc",
        "content": content,
    }


def build_execution_package(requirement_document: Dict, delivery_artifacts: Dict) -> Dict:
    return {
        "requirement_document": requirement_document,
        "epic": delivery_artifacts.get("epic", {}),
        "stories": delivery_artifacts.get("stories", []),
        "metadata": {
            "execution_status": "READY_FOR_JIRA_MAPPING",
            "project_key": JIRA_PROJECT_KEY,
        },
    }


def build_jira_payload(execution_package: Dict) -> Dict:
    epic = execution_package.get("epic", {})
    stories = execution_package.get("stories", [])

    epic_description_adf = text_to_adf_document(
        paragraphs=[
            epic.get("description", ""),
            f"Business Value: {epic.get('business_value', '')}",
            f"Success Metrics: {epic.get('success_metrics', '')}",
        ]
    )

    jira_payload = {
        "epic": {
            "fields": {
                "project": {
                    "key": JIRA_PROJECT_KEY
                },
                "summary": epic.get("title", "Generated Epic"),
                "description": epic_description_adf,
                "issuetype": {
                    "name": JIRA_EPIC_ISSUE_TYPE
                },
            }
        },
        "stories": [],
    }

    for story in stories:
        acceptance_criteria = story.get("acceptance_criteria", [])
        dependencies = story.get("dependencies", [])
        risks = story.get("risks", [])

        story_description_adf = text_to_adf_document(
            paragraphs=[
                story.get("description", ""),
            ],
            bullet_sections={
                "Acceptance Criteria": acceptance_criteria,
                "Dependencies": dependencies,
                "Risks": risks,
            },
        )

        jira_payload["stories"].append(
            {
                "fields": {
                    "project": {
                        "key": JIRA_PROJECT_KEY
                    },
                    "summary": story.get("title", "Generated Story"),
                    "description": story_description_adf,
                    "issuetype": {
                        "name": JIRA_STORY_ISSUE_TYPE
                    },
                }
            }
        )

    return jira_payload


def create_jira_issue(issue_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not jira_is_configured():
        raise ValueError("Jira is not fully configured. Check Jira environment variables.")

    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    headers = build_jira_auth_header()

    response = requests.post(url, headers=headers, json=issue_payload, timeout=60)

    if response.status_code not in (200, 201):
        raise ValueError(f"Jira issue creation failed: {response.status_code} - {response.text}")

    return response.json()


def submit_jira_payload(jira_payload: Dict) -> Dict:
    epic_payload = jira_payload.get("epic")
    story_payloads = jira_payload.get("stories", [])

    if not epic_payload:
        raise ValueError("Jira payload does not contain an epic.")

    epic_result = create_jira_issue(epic_payload)
    epic_key = epic_result.get("key")

    created_stories = []

    for payload in story_payloads:
        payload = payload.copy()
        fields = payload.setdefault("fields", {})
        fields["parent"] = {"key": epic_key}

        story_result = create_jira_issue(payload)
        created_stories.append(
            {
                "key": story_result.get("key"),
                "id": story_result.get("id"),
                "self": story_result.get("self"),
            }
        )

    return {
        "epic": {
            "key": epic_result.get("key"),
            "id": epic_result.get("id"),
            "self": epic_result.get("self"),
        },
        "stories": created_stories,
    }