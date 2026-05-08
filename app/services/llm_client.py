import json
import logging

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.models.chat import LlmAssignmentDecision
from app.models.summary import LlmTicketSummary

logger = logging.getLogger(__name__)


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


def label_is_allowed(label):
    for allowed_label in ALLOWED_LABELS:
        if allowed_label.lower() == label.lower():
            return True
    return False


def summarize_ticket(ticket):
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

            if ALLOWED_LABELS:
                if not label_is_allowed(result.label):
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


ASSIGNMENT_PROMPT_TEMPLATE = """You are a Jira assistant reading a chat message about a ticket.
Always produce a short, helpful English reply to the message author — never stay silent.
Additionally decide whether the message is an EXPLICIT self-assignment request from the author
(they want to take, pick up, claim, or be assigned the ticket). Mere discussion, questions, or comments
do not count as self-assignment. If unsure about self-assignment, set assign to false.

Return ONLY a JSON object with exactly two keys:
- "assign": boolean — true only on explicit self-assignment.
- "message": a non-empty short English reply (1-2 sentences). When assign is true, phrase it as a
  confirmation like "Ticket {ticket_key} assigned to {user_name}". Otherwise, reply contextually to
  the author's message: briefly acknowledge, answer, or ask a clarifying question.

No markdown, no code fences, no extra keys, no preamble, no trailing text.

Ticket: {ticket_key}
Author: {user_name}
Message: {text}"""


def generate_chat_reply(payload):
    prompt = ASSIGNMENT_PROMPT_TEMPLATE.format(
        ticket_key=payload.ticket_key or "(unknown)",
        user_name=payload.user_name,
        text=payload.text or "",
    )

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    body = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    total_attempts = settings.LLM_MAX_RETRIES + 1
    last_error = None

    for attempt in range(1, total_attempts + 1):
        logger.info(f"Sending chat reply request to Ollama for {payload.ticket_key} (attempt {attempt}/{total_attempts})")
        try:
            response = requests.post(url, json=body, timeout=120)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()

            parsed = json.loads(raw)
            decision = LlmAssignmentDecision.model_validate(parsed)
            if not decision.message.strip():
                raise ValueError("LLM returned empty reply message")

            logger.info(f"Ollama chat reply for {payload.ticket_key}: assign={decision.assign}")
            return decision

        except requests.RequestException as e:
            logger.error(f"Error requesting Ollama for chat reply {payload.ticket_key}: {e}")
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = e
            logger.warning(f"LLM chat reply invalid for {payload.ticket_key} on attempt {attempt}: {e}")

    logger.error(f"LLM returned invalid chat reply for {payload.ticket_key} after {total_attempts} attempts")
    raise last_error


    
