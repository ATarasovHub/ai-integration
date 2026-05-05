import json
import logging
import re

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.models.summary import LlmTicketSummary
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)

# Strict-JSON prompt. The model is also forced to valid JSON via Ollama's `format: "json"`.
PROMPT_TEMPLATE = """You are a development team assistant. You are given a Jira ticket.
Return ONLY a JSON object with exactly one key "summary" whose value is a 3-5 sentence
plain-text summary in English describing: the problem or task, current status, who is
responsible (if specified) and the priority. No markdown, no code fences, no extra keys,
no preamble, no trailing text.

Ticket:
ID: {key}
Title: {summary}
Description: {description}
Status: {status}
Assignee: {assignee}
Priority: {priority}
Reporter: {reporter}"""


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_summary(raw: str) -> str:
    # Try the raw response first, then fall back to the first {...} block we can find,
    # in case the model decided to wrap JSON in commentary despite the constraint.
    candidates = [raw]
    match = _JSON_BLOCK.search(raw)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            return LlmTicketSummary.model_validate(json.loads(candidate)).summary
        except (json.JSONDecodeError, ValidationError):
            continue

    raise ValueError(f"LLM did not return valid JSON: {raw[:200]}")


def summarize_ticket(ticket: JiraTicket) -> str:
    """Send ticket to Ollama and return the summary text parsed from strict JSON."""

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
        "stream": False,
        "format": "json",
    }

    logger.info(f"Sending ticket {ticket.key} to Ollama (model: {settings.OLLAMA_MODEL})")

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "").strip()
        summary = _extract_summary(raw)
        logger.info(f"Ollama returned summary for {ticket.key} ({len(summary)} characters)")
        return summary
    except requests.RequestException as e:
        logger.error(f"Error requesting Ollama: {e}")
        raise
