import logging
import requests

from config import settings
from models.ticket import JiraTicket

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a development team assistant. You are given a Jira ticket.
Write a brief summary (3-5 sentences) in English:
- What the problem or task is
- Current status
- Who is responsible (if specified)
- Priority

Ticket:
ID: {key}
Title: {summary}
Description: {description}
Status: {status}
Assignee: {assignee}
Priority: {priority}
Reporter: {reporter}

Summary:"""


def summarize_ticket(ticket: JiraTicket) -> str:
    """Send ticket to Ollama and get summary."""

    prompt = PROMPT_TEMPLATE.format(
        key=ticket.key,
        summary=ticket.summary,
        description=ticket.description,
        status=ticket.status,
        assignee=ticket.assignee or "Not assigned",
        priority=ticket.priority or "Not specified",
        reporter=ticket.reporter or "Not specified",
    )

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    logger.info(f"Sending ticket {ticket.key} to Ollama (model: {settings.OLLAMA_MODEL})")

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        summary = data.get("response", "").strip()
        logger.info(f"Ollama returned summary for {ticket.key} ({len(summary)} characters)")
        return summary
    except requests.RequestException as e:
        logger.error(f"Error requesting Ollama: {e}")
        raise
