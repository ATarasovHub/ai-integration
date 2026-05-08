import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from the local .env file.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    PROJECT_ROOT: Path = PROJECT_ROOT

    # Jira connection settings.
    JIRA_BASE_URL: str = os.getenv("JIRA_URL", os.getenv("JIRA_BASE_URL", "https://your-jira.example.com"))
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "your_jira_token")
    JIRA_EMAIL: str = os.getenv("JIRA_EMAIL", "")
    JIRA_USE_MOCK: bool = os.getenv("JIRA_USE_MOCK", "false").lower() == "true"
    # Optional JQL override for the standalone pipeline. When empty, defaults to open tickets.
    JIRA_JQL: str = os.getenv("JIRA_JQL", "status != Done ORDER BY created DESC")

    # Ollama API settings.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # LLM JSON validation retry budget (extra attempts after the first one).
    # The call gives up and raises after this many invalid-JSON responses in a row.
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "10"))


# Create one shared settings object for the application.
settings = Settings()
