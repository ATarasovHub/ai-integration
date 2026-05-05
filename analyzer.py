import json
import logging
import os
from typing import List, Optional

import requests

from config import settings
from models.analysis import AiAnalysisRequest, AiAnalysisResponse

logger = logging.getLogger(__name__)


# Built-in roster used when TEAM_ROSTER_PATH is missing.
# Keep skill tags short and task-oriented so the LLM can match them to ticket text.
DEFAULT_TEAM = [
    {
        "accountId": "ivan-petrov",
        "displayName": "Ivan Petrov",
        "skills": ["backend", "auth", "java", "spring", "production-incidents"],
    },
    {
        "accountId": "maria-sidorova",
        "displayName": "Maria Sidorova",
        "skills": ["frontend", "react", "ui", "ux"],
    },
    {
        "accountId": "alexey-kuznetsov",
        "displayName": "Alexey Kuznetsov",
        "skills": ["database", "performance", "sql", "pagination", "indexing"],
    },
]


# Prompt template instructs the model to pick an assignee from a fixed candidate pool.
PROMPT_TEMPLATE = """You route a Jira ticket to the most suitable team member.

Return JSON only with this exact schema:
{{
  "assigneeAccountId": string | null,
  "assigneeDisplayName": string | null,
  "confidence": number between 0 and 1,
  "reasoning": string
}}

Rules:
- Pick exactly one candidate from the team list, or null if no candidate clearly fits.
- assigneeAccountId and assigneeDisplayName must come verbatim from the team list, or both be null.
- Use confidence >= 0.8 only when the ticket clearly matches one candidate's skills.
- Lower confidence when description is missing, vague, or when several candidates would also fit.
- reasoning must be one short sentence in English.

Team:
{team}

Ticket:
key: {ticketKey}
summary: {summary}
description: {description}
priority: {priority}
"""


def _load_team() -> List[dict]:
    """Load the team roster from disk or fall back to the built-in sample."""
    path = settings.TEAM_ROSTER_PATH
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                roster = json.load(f)
            if isinstance(roster, list) and roster:
                return roster
            logger.warning("Team roster at %s is empty or not a list, using default", path)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load team roster from %s: %s — using default", path, e)
    return DEFAULT_TEAM


def _enforce_roster_match(team: List[dict], result: AiAnalysisResponse) -> AiAnalysisResponse:
    """Drop assignee fields if the LLM hallucinated a name that is not in the roster."""
    if result.assigneeAccountId is None and result.assigneeDisplayName is None:
        return result
    valid_ids = {member.get("accountId") for member in team}
    valid_names = {member.get("displayName") for member in team}
    if result.assigneeAccountId not in valid_ids or result.assigneeDisplayName not in valid_names:
        logger.warning("LLM returned assignee %s/%s that is not in the roster — clearing it", result.assigneeAccountId, result.assigneeDisplayName)
        result.assigneeAccountId = None
        result.assigneeDisplayName = None
        # Force fallback path on the Java side: zero confidence triggers Rocket.Chat escalation.
        result.confidence = 0.0
    return result


def analyze_ticket(request: AiAnalysisRequest) -> AiAnalysisResponse:
    """Pick the best assignee for a Jira ticket from the configured team roster."""
    team = _load_team()

    # Render the team list as compact JSON inside the prompt.
    prompt = PROMPT_TEMPLATE.format(
        team=json.dumps(team, ensure_ascii=False),
        ticketKey=request.ticketKey,
        summary=request.summary,
        description=request.description or "No description available",
        priority=request.priority or "Not specified",
    )

    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    logger.info("Analyzing ticket %s for assignee routing (model: %s, candidates: %s)", request.ticketKey, settings.OLLAMA_MODEL, len(team))

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "").strip()
        parsed = json.loads(raw)
        result = AiAnalysisResponse.model_validate(parsed)
        result = _enforce_roster_match(team, result)
        logger.info("Ticket %s routed to %s (confidence=%s)", request.ticketKey, result.assigneeDisplayName or "none", result.confidence)
        return result
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        logger.error("Error analyzing ticket %s: %s", request.ticketKey, e)
        raise
