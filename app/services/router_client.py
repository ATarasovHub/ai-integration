import logging
import requests

from app.core.config import settings
from app.models.summary import RocketChatMessage

logger = logging.getLogger(__name__)


def send_to_router(message: RocketChatMessage) -> None:
    """Forward a Rocket.Chat-ready message to ticket_router_api.

    The Java router owns posting to Rocket.Chat — this service only delivers the payload.
    """
    if settings.TICKET_ROUTER_USE_MOCK:
        logger.info(f"[MOCK] Message for ticket_router_api ({message.ticketKey}):\n{message.text}")
        return

    url = f"{settings.TICKET_ROUTER_BASE_URL}/api/rocketchat/messages"
    payload = {"ticketKey": message.ticketKey, "text": message.text}

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Message for {message.ticketKey} forwarded to ticket_router_api")
    except requests.RequestException as e:
        logger.error(f"Error forwarding {message.ticketKey} to ticket_router_api: {e}")
        raise
