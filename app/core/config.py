import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from the local .env file.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    PROJECT_ROOT: Path = PROJECT_ROOT

    # Jira connection settings.
    JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "https://your-jira.example.com")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "your_jira_token")
    JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "MYPROJECT")
    JIRA_USE_MOCK: bool = os.getenv("JIRA_USE_MOCK", "true").lower() == "true"

    # Ollama API settings.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # ticket_router_api connection settings — Rocket.Chat is owned by the Java router.
    TICKET_ROUTER_BASE_URL: str = os.getenv("TICKET_ROUTER_BASE_URL", "http://localhost:8080/ticket-router-api")
    TICKET_ROUTER_USE_MOCK: bool = os.getenv("TICKET_ROUTER_USE_MOCK", "true").lower() == "true"


# Create one shared settings object for the application.
settings = Settings()
