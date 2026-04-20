import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Jira ---
    JIRA_BASE_URL: str = os.getenv("JIRA_BASE_URL", "https://your-jira.example.com")
    JIRA_API_TOKEN: str = os.getenv("JIRA_API_TOKEN", "your_jira_token")
    JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "MYPROJECT")
    JIRA_USE_MOCK: bool = os.getenv("JIRA_USE_MOCK", "true").lower() == "true"

    # --- Ollama ---
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # --- Rocket.Chat ---
    ROCKETCHAT_BASE_URL: str = os.getenv("ROCKETCHAT_BASE_URL", "https://your-rocketchat.example.com")
    ROCKETCHAT_TOKEN: str = os.getenv("ROCKETCHAT_TOKEN", "your_rc_token")
    ROCKETCHAT_USER_ID: str = os.getenv("ROCKETCHAT_USER_ID", "your_rc_user_id")
    ROCKETCHAT_CHANNEL: str = os.getenv("ROCKETCHAT_CHANNEL", "#general")
    ROCKETCHAT_USE_MOCK: bool = os.getenv("ROCKETCHAT_USE_MOCK", "true").lower() == "true"


settings = Settings()
