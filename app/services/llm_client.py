import json
import logging

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.models.summary import LlmTicketSummary
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)


# Load allowed labels from a file once at startup.
labels_path = settings.PROJECT_ROOT / "app" / "data" / "jira_labels.json"
try:
    ALLOWED_LABELS = json.loads(labels_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    logger.warning(f"Jira labels file not found at {labels_path}")
    ALLOWED_LABELS = []


PROMPT_TEMPLATE = """You are a development team assistant. You are given a Jira ticket.
Return ONLY a JSON object with exactly two keys:
- "summary": a 3-5 sentence plain-text summary in English describing the problem or task,
  current status, who is responsible (if specified) and the priority.
- "label": exactly one value chosen from the allowed labels list below that best matches
  the ticket. Copy the label verbatim, preserving case. Do not invent new labels.

Allowed labels: {labels}

No markdown, no code fences, no extra keys, no preamble, no trailing text.

Ticket:
ID: {key}
Title: {summary}
Description: {description}
Status: {status}
Assignee: {assignee}
Priority: {priority}
Reporter: {reporter}"""


def summarize_ticket(ticket: JiraTicket) -> LlmTicketSummary:
    """Send ticket to Ollama and return parsed summary with a label."""

    if ALLOWED_LABELS:
        labels_str = ", ".join(ALLOWED_LABELS)
    else:
        labels_str = "(none configured)"

    prompt = PROMPT_TEMPLATE.format(
        labels=labels_str,
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

    total_attempts = settings.LLM_MAX_RETRIES + 1
    last_error = None

    for attempt in range(1, total_attempts + 1):
        logger.info(f"Sending ticket {ticket.key} to Ollama (attempt {attempt}/{total_attempts})")
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()

            parsed = json.loads(raw)
            result = LlmTicketSummary.model_validate(parsed)

            # Check that the label is in the allowed list.
            if ALLOWED_LABELS:
                allowed_lower = [label.lower() for label in ALLOWED_LABELS]
                if result.label.lower() not in allowed_lower:
                    raise ValueError(f"LLM returned label '{result.label}' not in allowed list")

            logger.info(f"Ollama returned summary for {ticket.key}, label={result.label}")
            return result

        except requests.RequestException as e:
            logger.error(f"Error requesting Ollama for {ticket.key}: {e}")
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            logger.warning(f"LLM response invalid for {ticket.key} on attempt {attempt}: {e}")

    logger.error(f"LLM returned invalid response for {ticket.key} after {total_attempts} attempts")
    raise last_error
