import asyncio
import unittest
from unittest.mock import patch

from app import main
from app.models.summary import LlmTicketSummary, TicketSummaryResponse
from app.models.ticket import JiraTicket, JiraTicketPayload, JiraTicketsBatchPayload


class PipelineTests(unittest.TestCase):
    def test_process_tickets_pipeline_returns_no_tickets_status(self) -> None:
        with patch("app.main.get_tickets", return_value=[]):
            result = asyncio.run(main.process_tickets_pipeline())

        self.assertEqual(result, {"status": "no_tickets"})

    def test_process_tickets_pipeline_continues_after_one_ticket_fails(self) -> None:
        tickets = [
            JiraTicket(key="ATM-30", summary="First", description="First", status="Open"),
            JiraTicket(key="ATM-31", summary="Second", description="Second", status="Open"),
        ]

        def process(ticket: JiraTicket) -> dict:
            if ticket.key == "ATM-30":
                raise RuntimeError("LLM unavailable")
            return {"ticket": ticket.key, "status": "ok", "summary": "Done", "label": "general"}

        with (
            patch("app.main.get_tickets", return_value=tickets),
            patch("app.main.process_ticket", side_effect=process),
        ):
            result = asyncio.run(main.process_tickets_pipeline())

        self.assertEqual(
            result,
            [
                {"ticket": "ATM-30", "status": "error", "detail": "LLM unavailable"},
                {"ticket": "ATM-31", "status": "ok", "summary": "Done", "label": "general"},
            ],
        )

    def test_summarize_only_returns_structured_response(self) -> None:
        ticket = JiraTicket(key="ATM-32", summary="Sync labels", description="Labels drift.", status="Open")

        with patch(
            "app.main.summarize_ticket",
            return_value=LlmTicketSummary(summary="Labels need to be synced.", label="general"),
        ):
            response = main.summarize_only(ticket)

        self.assertEqual(
            response,
            TicketSummaryResponse(ticket="ATM-32", summary="Labels need to be synced.", label="general"),
        )

    def test_batch_endpoint_skips_failed_ticket_and_keeps_successes(self) -> None:
        payload = JiraTicketsBatchPayload(
            tickets=[
                JiraTicketPayload(key="ATM-33", summary="Good ticket"),
                JiraTicketPayload(key="ATM-34", summary="Bad ticket"),
            ]
        )

        def summarize(ticket: JiraTicket) -> TicketSummaryResponse:
            if ticket.key == "ATM-34":
                raise RuntimeError("bad ticket")
            return TicketSummaryResponse(ticket=ticket.key, summary="ok", label="general")

        with patch("app.main.summarize_only", side_effect=summarize):
            result = asyncio.run(main.process_tickets_batch(payload))

        self.assertEqual(
            result,
            [TicketSummaryResponse(ticket="ATM-33", summary="ok", label="general")],
        )


if __name__ == "__main__":
    unittest.main()
