import unittest
from unittest.mock import Mock, patch

import requests

from app.services import jira_client


class JiraClientTests(unittest.TestCase):
    def test_parse_ticket_uses_safe_defaults_for_missing_optional_fields(self) -> None:
        ticket = jira_client._parse_ticket(
            {
                "key": "ATM-10",
                "fields": {
                    "summary": "Fix export",
                    "description": None,
                    "status": {},
                    "assignee": None,
                    "priority": None,
                    "reporter": None,
                },
            }
        )

        self.assertEqual(ticket.key, "ATM-10")
        self.assertEqual(ticket.summary, "Fix export")
        self.assertEqual(ticket.description, "No description available")
        self.assertEqual(ticket.status, "Unknown")
        self.assertIsNone(ticket.assignee)
        self.assertIsNone(ticket.priority)
        self.assertIsNone(ticket.reporter)

    def test_get_tickets_mock_mode_does_not_call_jira(self) -> None:
        with (
            patch.object(jira_client.settings, "JIRA_USE_MOCK", True),
            patch("app.services.jira_client.requests.get") as get,
        ):
            tickets = jira_client.get_tickets()

        self.assertGreaterEqual(len(tickets), 1)
        self.assertEqual(tickets[0].key, "MYPROJECT-1")
        get.assert_not_called()

    def test_get_tickets_real_mode_posts_expected_search_request(self) -> None:
        response = Mock()
        response.json.return_value = {
            "issues": [
                {
                    "key": "ATM-11",
                    "fields": {
                        "summary": "Add dashboard filter",
                        "description": "Support filtering by owner.",
                        "status": {"name": "To Do"},
                        "assignee": {"displayName": "Ivan"},
                        "priority": {"name": "Medium"},
                        "reporter": {"displayName": "Maria"},
                    },
                }
            ]
        }

        with (
            patch.object(jira_client.settings, "JIRA_USE_MOCK", False),
            patch.object(jira_client.settings, "JIRA_BASE_URL", "https://jira.example.test"),
            patch.object(jira_client.settings, "JIRA_JQL", "project=ATM AND status != Done ORDER BY created DESC"),
            patch.object(jira_client.settings, "JIRA_API_TOKEN", "token-123"),
            patch("app.services.jira_client.requests.get", return_value=response) as get,
        ):
            tickets = jira_client.get_tickets()

        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0].key, "ATM-11")
        get.assert_called_once()
        _, kwargs = get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token-123")
        self.assertEqual(kwargs["params"]["jql"], "project=ATM AND status != Done ORDER BY created DESC")
        self.assertEqual(kwargs["params"]["fields"], "summary,description,status,assignee,priority,reporter")

    def test_get_tickets_returns_empty_list_when_jira_request_fails(self) -> None:
        with (
            patch.object(jira_client.settings, "JIRA_USE_MOCK", False),
            patch(
                "app.services.jira_client.requests.get",
                side_effect=requests.Timeout("jira timed out"),
            ),
        ):
            tickets = jira_client.get_tickets()

        self.assertEqual(tickets, [])


if __name__ == "__main__":
    unittest.main()
