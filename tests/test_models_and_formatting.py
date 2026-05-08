import unittest

from app.models.ticket import JiraTicketPayload


class ModelsTests(unittest.TestCase):
    def test_ticket_payload_converts_to_domain_with_defaults(self) -> None:
        ticket = JiraTicketPayload(key="ATM-20", summary="Investigate billing").to_domain()

        self.assertEqual(ticket.key, "ATM-20")
        self.assertEqual(ticket.description, "No description available")
        self.assertEqual(ticket.status, "Unknown")
        self.assertIsNone(ticket.assignee)


if __name__ == "__main__":
    unittest.main()
