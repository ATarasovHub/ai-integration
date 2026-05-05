import logging
import requests

from app.core.config import settings
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)


def format_message(ticket: JiraTicket, summary: str) -> str:
    # Build the final Rocket.Chat message text from ticket data and the AI summary.
    return (
        f"📋 *Ticket {ticket.key}* | {ticket.status} | 🔥 {ticket.priority or 'N/A'}\n"
        f"*{ticket.summary}*\n\n"
        f"{summary}\n\n"
        f"👤 Assignee: {ticket.assignee or 'Not assigned'}"
    )


def send_summary(ticket: JiraTicket, summary: str) -> None:
    """Send ticket summary to Rocket.Chat."""

    # Prepare the text that will be posted to the configured channel.
    message = format_message(ticket, summary)

    # In mock mode, log the message instead of sending it.
    if settings.ROCKETCHAT_USE_MOCK:
        logger.info(f"[MOCK] Message for Rocket.Chat ({ticket.key}):\n{message}")
        return

    # Build the real Rocket.Chat API request.
    url = f"{settings.ROCKETCHAT_BASE_URL}/api/v1/chat.postMessage"
    headers = {
        "X-Auth-Token": settings.ROCKETCHAT_TOKEN,
        "X-User-Id": settings.ROCKETCHAT_USER_ID,
        "Content-Type": "application/json"
    }
    payload = {
        "channel": settings.ROCKETCHAT_CHANNEL,
        "text": message
    
    }

    # Send the message and raise an error if Rocket.Chat rejects the request.
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Message for {ticket.key} successfully sent to Rocket.Chat")
    except requests.RequestException as e:
        logger.error(f"Error sending to Rocket.Chat: {e}")
        raise
