#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "app" / "data" / "jira_labels.json"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("your_"):
        raise RuntimeError(f"{name} is not configured")
    return value


def fetch_labels(base_url: str, token: str, jql: str, limit: int, email: str = "") -> list[str]:
    url = f"{base_url.rstrip('/')}/rest/api/2/search"
    headers = {"Content-Type": "application/json"}
    auth = None
    if email:
        # Atlassian Cloud style: Basic auth with email + API token.
        auth = (email, token)
    else:
        # Jira Server/DC: Personal Access Token via Bearer header.
        headers["Authorization"] = f"Bearer {token}"

    labels: set[str] = set()
    fetched = 0

    while fetched < limit:
        batch_size = min(100, limit - fetched)
        params = {
            "jql": jql,
            "startAt": fetched,
            "maxResults": batch_size,
            "fields": "labels",
        }

        response = requests.get(url, headers=headers, params=params, auth=auth, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Jira returned {response.status_code}: {response.text}")
        payload = response.json()
        issues = payload.get("issues", [])

        for issue in issues:
            for label in issue.get("fields", {}).get("labels") or []:
                if label:
                    labels.add(label)

        fetched += len(issues)
        if not issues or fetched >= payload.get("total", 0):
            break

    return sorted(labels, key=str.casefold)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Export unique Jira labels from the latest project tickets.")
    parser.add_argument("--limit", type=int, default=100, help="How many Jira issues to inspect.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to save labels JSON.")
    parser.add_argument("--jql", default=None, help="Override Jira JQL.")
    args = parser.parse_args()

    base_url = os.getenv("JIRA_URL", "").strip() or _required_env("JIRA_BASE_URL")
    token = _required_env("JIRA_API_TOKEN")
    email = os.getenv("JIRA_EMAIL", "").strip()
    project_key = os.getenv("JIRA_PROJECT_KEY", "").strip()
    env_jql = os.getenv("JIRA_LABELS_JQL", "").strip()
    if args.jql:
        jql = args.jql
    elif env_jql:
        jql = env_jql
    elif project_key:
        jql = f"project={project_key} ORDER BY created DESC"
    else:
        raise RuntimeError("Set JIRA_PROJECT_KEY or JIRA_LABELS_JQL in .env, or pass --jql")

    labels = fetch_labels(base_url=base_url, token=token, jql=jql, limit=args.limit, email=email)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(labels)} unique labels to {args.output}")


if __name__ == "__main__":
    main()
