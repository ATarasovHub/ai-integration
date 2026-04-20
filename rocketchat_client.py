import logging
import requests

from config import settings
from models.ticket import JiraTicket

logger = logging.getLogger(__name__)


def _format_message(ticket: JiraTicket, summary: str) -> str:

    return (
        f"📋 *Ticket {ticket.key}* | {ticket.status} | 🔥 {ticket.priority or 'N/A'}\n"
        f"*{ticket.summary}*\n\n"
        f"{summary}\n\n"
        f"👤 Assignee: {ticket.assignee or 'Not assigned'}"
    )


def send_summary(ticket: JiraTicket, summary: str) -> None:
    """Send ticket summary to Rocket.Chat."""

    message = _format_message(ticket, summary)

    if settings.ROCKETCHAT_USE_MOCK:
        logger.info(f"[MOCK] Message for Rocket.Chat ({ticket.key}):\n{message}")
        return

    # --- Real Rocket.Chat API request ---
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

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info(f"Message for {ticket.key} successfully sent to Rocket.Chat")
    except requests.RequestException as e:
        logger.error(f"Error sending to Rocket.Chat: {e}")
        raise
