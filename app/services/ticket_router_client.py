import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_rocket_message(ticket_key: str, text: str) -> None:
    """Send a Rocket.Chat message via ticket_router_api."""
    url = f"{settings.TICKET_ROUTER_BASE_URL.rstrip('/')}/api/rocketchat/messages"
    payload = {"ticketKey": ticket_key, "text": text}

    logger.info(f"Posting Rocket.Chat message via ticket_router for {ticket_key}")
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
