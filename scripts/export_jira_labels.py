#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "app" / "data" / "jira_labels.json"
DEFAULT_JQL = "status != Done ORDER BY created DESC"


def get_env(name, default=""):
    value = os.getenv(name, default)
    if value is None:
        return ""
    return value.strip()


def is_bad_value(value):
    return value == "" or value.startswith("your_") or "your-jira" in value


def check_env(name):
    value = get_env(name)
    if is_bad_value(value):
        raise RuntimeError(name + " is not configured")
    return value


def fetch_labels(base_url, token, jql, limit, email=""):
    url = f"{base_url.rstrip('/')}/rest/api/2/search"
    headers = {"Content-Type": "application/json"}
    auth = None

    if email:
        auth = (email, token)
    else:
        headers["Authorization"] = f"Bearer {token}"

    labels = []
    fetched = 0

    while fetched < limit:
        batch_size = min(100, limit - fetched)
        params = {
            "jql": jql,
            "startAt": fetched,
            "maxResults": batch_size,
            "fields": "labels",
        }

        try:
            response = requests.get(url, headers=headers, params=params, auth=auth, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise RuntimeError("Jira request failed: " + str(error)) from error
        except ValueError as error:
            raise RuntimeError("Jira returned bad JSON") from error

        issues = payload.get("issues", [])

        for issue in issues:
            for label in issue.get("fields", {}).get("labels") or []:
                if label and label not in labels:
                    labels.append(label)

        fetched += len(issues)
        if not issues or fetched >= payload.get("total", 0):
            break

    labels.sort(key=str.lower)
    return labels


def save_labels(labels, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(labels, ensure_ascii=False, indent=2)
    output_file.write_text(text + "\n", encoding="utf-8")


def main():
    load_dotenv(PROJECT_ROOT / ".env")

    parser = argparse.ArgumentParser(description="Export Jira labels to JSON.")
    parser.add_argument("--limit", type=int, default=100, help="How many Jira issues to check.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output json file.")
    parser.add_argument("--jql", default="", help="Jira JQL.")
    args = parser.parse_args()

    if args.limit < 1:
        print("limit must be more than 0")
        return 1

    try:
        base_url = get_env("JIRA_URL") or get_env("JIRA_BASE_URL")
        if is_bad_value(base_url):
            raise RuntimeError("JIRA_BASE_URL is not configured")

        token = check_env("JIRA_API_TOKEN")
        email = get_env("JIRA_EMAIL")

        if args.jql:
            jql = args.jql
        else:
            jql = get_env("JIRA_LABELS_JQL") or get_env("JIRA_JQL", DEFAULT_JQL)

        labels = fetch_labels(base_url, token, jql, args.limit, email)
        save_labels(labels, args.output)
    except RuntimeError as error:
        print("Error: " + str(error))
        return 1

    print("Saved " + str(len(labels)) + " labels to " + str(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
