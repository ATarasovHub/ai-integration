import json
import logging
import re

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.models.summary import LlmTicketSummary
from app.models.ticket import JiraTicket

logger = logging.getLogger(__name__)


def _load_labels() -> list[str]:
    path = settings.PROJECT_ROOT / "app" / "data" / "jira_labels.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("Jira labels file not found at %s — label selection disabled", path)
        return []


ALLOWED_LABELS: list[str] = _load_labels()
_ALLOWED_LABELS_SET: set[str] = {label.casefold() for label in ALLOWED_LABELS}

# Strict-JSON prompt. The model is also forced to valid JSON via Ollama's `format: "json"`.
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


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _extract_summary(raw: str) -> LlmTicketSummary:
    # Try the raw response first, then fall back to the first {...} block we can find,
    # in case the model decided to wrap JSON in commentary despite the constraint.
    candidates = [raw]
    match = _JSON_BLOCK.search(raw)
    if match:
        candidates.append(match.group(0))

    last_err: Exception | None = None
    for candidate in candidates:
        try:
            result = LlmTicketSummary.model_validate(json.loads(candidate))
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            continue
        if _ALLOWED_LABELS_SET and result.label.casefold() not in _ALLOWED_LABELS_SET:
            raise ValueError(f"LLM returned label '{result.label}' not in allowed list")
        return result

    raise ValueError(f"LLM did not return valid JSON: {raw[:200]}") from last_err


def summarize_ticket(ticket: JiraTicket) -> LlmTicketSummary:
    """Send ticket to Ollama and return the summary + chosen label parsed from strict JSON.

    On malformed JSON or an out-of-list label we retry up to settings.LLM_MAX_RETRIES
    times. If the model keeps producing invalid responses for that many attempts in a
    row, the last error is re-raised so the caller decides what to do.
    """

    prompt = PROMPT_TEMPLATE.format(
        labels=", ".join(ALLOWED_LABELS) if ALLOWED_LABELS else "(none configured)",
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

    total_attempts = max(1, settings.LLM_MAX_RETRIES + 1)
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        logger.info(f"Sending ticket {ticket.key} to Ollama (model: {settings.OLLAMA_MODEL}, attempt {attempt}/{total_attempts})")
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "").strip()
            result = _extract_summary(raw)
            logger.info(f"Ollama returned summary for {ticket.key} ({len(result.summary)} chars, label={result.label})")
            return result
        except requests.RequestException as e:
            logger.error(f"Error requesting Ollama for {ticket.key}: {e}")
            raise
        except ValueError as e:
            last_error = e
            logger.warning(f"LLM JSON validation failed for {ticket.key} on attempt {attempt}/{total_attempts}: {e}")

    logger.error(f"LLM returned invalid JSON for ticket {ticket.key} after {total_attempts} attempts")
    raise last_error if last_error else ValueError(f"LLM did not return valid JSON for ticket {ticket.key}")
