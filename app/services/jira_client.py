import logging
import requests
from typing import List

from app.core.config import settings
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)

# Local example tickets used when the Jira mock mode is enabled.
MOCK_TICKETS = [
    {
        "key": "MYPROJECT-1",
        "fields": {
            "summary": "Authorization service crashing in prod",
            "description": "After deploying v2.3.1, users cannot log in. Error 503 in logs.",
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Ivan Petrov"},
            "priority": {"name": "Critical"},
            "reporter": {"displayName": "Maria Sidorova"},
        }
    },
    {
        "key": "MYPROJECT-2",
        "fields": {
            "summary": "Add pagination to orders list",
            "description": "Orders page loads all records at once — slows down with >1000 rows.",
            "status": {"name": "To Do"},
            "assignee": None,
            "priority": {"name": "Medium"},
            "reporter": {"displayName": "Alexey Kuznetsov"},
        }
    },
]


def _parse_ticket(raw: dict) -> JiraTicket:
    """Parse raw JSON from Jira API into dataclass."""
    # Convert Jira's nested API response into the simpler internal ticket model.
    fields = raw.get("fields", {})
    return JiraTicket(
        key=raw.get("key", "UNKNOWN"),
        summary=fields.get("summary", ""),
        description=fields.get("description") or "No description available",
        status=fields.get("status", {}).get("name", "Unknown"),
        assignee=fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        priority=fields.get("priority", {}).get("name") if fields.get("priority") else None,
        reporter=fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
    )


def get_tickets() -> List[JiraTicket]:
    """Get tickets from Jira. Returns list of JiraTicket."""

    # In mock mode, return local sample tickets without calling Jira.
    if settings.JIRA_USE_MOCK:
        logger.info("[MOCK] Using mock Jira tickets")
        return [_parse_ticket(t) for t in MOCK_TICKETS]

    # Build the real Jira API request for open project tickets.
    url = f"{settings.JIRA_BASE_URL}/rest/api/2/search"
    params = {
        "jql": f"project={settings.JIRA_PROJECT_KEY} AND status != Done ORDER BY created DESC",
        "maxResults": 10,
        "fields": "summary,description,status,assignee,priority,reporter"
    }
    headers = {
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Send the request and parse every returned issue into the internal model.
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        issues = response.json().get("issues", [])
        logger.info(f"Received {len(issues)} tickets from Jira")
        return [_parse_ticket(issue) for issue in issues]
    except requests.RequestException as e:
        logger.error(f"Error requesting Jira: {e}")
        return []
