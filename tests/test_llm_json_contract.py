import json
import unittest
from unittest.mock import patch

from app.models.reply import RocketChatReply
from app.models.ticket import JiraTicket
from app.services import llm_client, reply_classifier


class FakeOllamaResponse:
    def __init__(self, raw_response: str) -> None:
        self.raw_response = raw_response

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"response": self.raw_response}


class LlmJsonContractTests(unittest.TestCase):
    def test_summarize_ticket_retries_until_exact_summary_schema(self) -> None:
        ticket = JiraTicket(
            key="ATM-1",
            summary="Broken SMS routing",
            description="Messages are not delivered to the partner route.",
            status="Open",
            assignee="Ivan",
            priority="High",
            reporter="Maria",
        )
        invalid_extra_key = json.dumps(
            {
                "summary": "The ticket reports an SMS routing failure. Ivan owns the work. Priority is high.",
                "label": "general",
                "extra": "not allowed",
            }
        )
        valid = json.dumps(
            {
                "summary": "The ticket reports an SMS routing failure. Ivan owns the work. Priority is high.",
                "label": "general",
            }
        )

        with (
            patch.object(llm_client.settings, "LLM_MAX_RETRIES", 1),
            patch("app.services.llm_client.requests.post") as post,
        ):
            post.side_effect = [FakeOllamaResponse(invalid_extra_key), FakeOllamaResponse(valid)]

            result = llm_client.summarize_ticket(ticket)

        self.assertEqual(result.label, "general")
        self.assertEqual(post.call_count, 2)

    def test_summarize_ticket_rejects_unknown_label(self) -> None:
        ticket = JiraTicket(
            key="ATM-2",
            summary="Broken billing export",
            description="The export file is empty.",
            status="Open",
        )
        unknown_label = json.dumps(
            {
                "summary": "The ticket reports an empty billing export. No owner is specified. Priority is not specified.",
                "label": "invented-label",
            }
        )

        with (
            patch.object(llm_client.settings, "LLM_MAX_RETRIES", 0),
            patch("app.services.llm_client.requests.post", return_value=FakeOllamaResponse(unknown_label)),
            self.assertRaises(ValueError),
        ):
            llm_client.summarize_ticket(ticket)

    def test_classify_reply_retries_until_exact_reply_schema(self) -> None:
        reply = RocketChatReply(
            ticket_key="ATM-3",
            source_message_id="rocket-msg-1",
            parent_message_id="rocket-parent-1",
            source_user_id="user-1",
            source_username="ivan",
            text="I will take it.",
        )
        invalid_extra_key = json.dumps(
            {
                "source_message_id": "rocket-msg-1",
                "source_user_id": "user-1",
                "confirmed_to_take": True,
                "clarification_response": None,
                "extra": "not allowed",
            }
        )
        valid = json.dumps(
            {
                "source_message_id": "rocket-msg-1",
                "source_user_id": "user-1",
                "confirmed_to_take": True,
                "clarification_response": None,
            }
        )

        with (
            patch.object(reply_classifier.settings, "LLM_MAX_RETRIES", 1),
            patch("app.services.reply_classifier.requests.post") as post,
        ):
            post.side_effect = [FakeOllamaResponse(invalid_extra_key), FakeOllamaResponse(valid)]

            result = reply_classifier.classify_reply(reply)

        self.assertTrue(result.confirmed_to_take)
        self.assertEqual(post.call_count, 2)

    def test_classify_reply_retries_on_mismatched_identifiers(self) -> None:
        reply = RocketChatReply(
            ticket_key="ATM-4",
            source_message_id="rocket-msg-2",
            parent_message_id="rocket-parent-2",
            source_user_id="user-2",
            source_username="maria",
            text="I need logs before I can take this.",
        )
        wrong_ids = json.dumps(
            {
                "source_message_id": "other-message",
                "source_user_id": "other-user",
                "confirmed_to_take": False,
                "clarification_response": "The user asks for logs before accepting ownership.",
            }
        )
        valid = json.dumps(
            {
                "source_message_id": "rocket-msg-2",
                "source_user_id": "user-2",
                "confirmed_to_take": False,
                "clarification_response": "The user asks for logs before accepting ownership.",
            }
        )

        with (
            patch.object(reply_classifier.settings, "LLM_MAX_RETRIES", 1),
            patch("app.services.reply_classifier.requests.post") as post,
        ):
            post.side_effect = [FakeOllamaResponse(wrong_ids), FakeOllamaResponse(valid)]

            result = reply_classifier.classify_reply(reply)

        self.assertFalse(result.confirmed_to_take)
        self.assertEqual(result.source_message_id, reply.source_message_id)
        self.assertEqual(result.source_user_id, reply.source_user_id)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
