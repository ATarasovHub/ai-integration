import json
import logging
from pathlib import Path

import requests
from app.core.config import settings
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)

MOCK_TICKETS_PATH = Path(__file__).resolve().parents[1] / "data" / "mock_tickets.json"
MOCK_TICKETS = json.loads(MOCK_TICKETS_PATH.read_text(encoding="utf-8"))


def _get_display_name(fields, name):
    value = fields.get(name)
    if value:
        return value.get("displayName")
    return None


def _get_name(fields, name):
    value = fields.get(name)
    if value:
        return value.get("name")
    return None


def _parse_ticket(raw):
    fields = raw.get("fields", {})

    return JiraTicket(
        key=raw.get("key", "UNKNOWN"),
        summary=fields.get("summary", ""),
        description=fields.get("description") or "No description available",
        status=fields.get("status", {}).get("name", "Unknown"),
        assignee=_get_display_name(fields, "assignee"),
        priority=_get_name(fields, "priority"),
        reporter=_get_display_name(fields, "reporter"),
    )


def get_tickets():
    if settings.JIRA_USE_MOCK:
        logger.info("[MOCK] Using mock Jira tickets")
        return [_parse_ticket(t) for t in MOCK_TICKETS]

    url = f"{settings.JIRA_BASE_URL}/rest/api/2/search"
    params = {
        "jql": settings.JIRA_JQL,
        "maxResults": 10,
        "fields": "summary,description,status,assignee,priority,reporter"
    }
    headers = {
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}" ,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        issues = response.json().get("issues", [])
        logger.info(f"Received {len(issues)} tickets from Jira")
        return [_parse_ticket(issue) for issue in issues]
    except requests.RequestException as e:
        logger.error(f"Error requesting Jira: {e}")
        return []
