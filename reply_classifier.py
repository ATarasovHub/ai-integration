import json
import logging
import requests

from config import settings
from models.reply import ReplyDecision, RocketChatReply

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You classify a single Rocket.Chat reply about taking ownership of a Jira ticket.

Return JSON only with this exact schema:
{{
  "source_message_id": "{source_message_id}",
  "source_user_id": "{source_user_id}",
  "confirmed_to_take": boolean,
  "clarification_response": string | null
}}

Rules:
- confirmed_to_take=true only when the user clearly says they will take or own the ticket.
- confirmed_to_take=false when the user declines, asks for clarification, postpones, or the message is not a clear acceptance.
- If confirmed_to_take=false, clarification_response must contain a short explanation based on the message text.
- If confirmed_to_take=true, clarification_response must be null.
- Do not invent facts outside the message.

Context:
ticket_key: {ticket_key}
parent_message_id: {parent_message_id}
source_username: {source_username}
message_text: {text}
"""


def classify_reply(reply: RocketChatReply) -> ReplyDecision:
    prompt = PROMPT_TEMPLATE.format(
        ticket_key=reply.ticket_key,
        source_message_id=reply.source_message_id,
        parent_message_id=reply.parent_message_id,
        source_user_id=reply.source_user_id,
        source_username=reply.source_username or "unknown",
        text=reply.text,
    )

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    logger.info(
        "Classifying Rocket.Chat reply %s from user %s",
        reply.source_message_id,
        reply.source_user_id,
    )

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        raw_response = data.get("response", "").strip()
        parsed = json.loads(raw_response)
        decision = ReplyDecision.model_validate(parsed)
        logger.info(
            "Reply %s classified: confirmed_to_take=%s",
            decision.source_message_id,
            decision.confirmed_to_take,
        )
        return decision
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        logger.error("Error classifying reply %s: %s", reply.source_message_id, e)
        raise
