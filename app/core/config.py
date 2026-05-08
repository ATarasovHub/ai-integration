import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    PROJECT_ROOT = PROJECT_ROOT

    JIRA_BASE_URL = os.getenv("JIRA_URL") or os.getenv("JIRA_BASE_URL", "https://your-jira.example.com")
    JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "your_jira_token")
    JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
    JIRA_USE_MOCK = os.getenv("JIRA_USE_MOCK", "false").lower() == "true"
    JIRA_JQL = os.getenv("JIRA_JQL", "status != Done ORDER BY created DESC")

    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    try:
        LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "10"))
    except ValueError:
        LLM_MAX_RETRIES = 10

    TICKET_ROUTER_BASE_URL = os.getenv("TICKET_ROUTER_BASE_URL", "http://localhost:8080")


settings = Settings()
