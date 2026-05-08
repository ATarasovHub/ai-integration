<div align="center">

# 🤖 aiIntegration

### Automatic AI Digest of Tasks for the Development Team

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-llama3-black?style=flat&logo=ollama&logoColor=white)](https://ollama.com)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat)](LICENSE)

</div>

---

## 📌 About

**aiIntegration** is the AI brain for ticket processing: it pulls open tickets from Jira, summarizes each via a local LLM (Ollama), classifies it with one of the allowed Jira labels, and returns the structured result. It also acts on Rocket.Chat messages forwarded by `ticket_router_api`: the LLM decides whether a chat message is an explicit self-assignment request for a ticket, and if so the service posts a confirmation back to Rocket.Chat through `ticket_router_api`. Direct delivery to chat platforms is otherwise out of scope.

> **Fully on-premise:** data never leaves your infrastructure. Jira and the LLM run locally.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔄 **2-stage pipeline** | Jira → LLM summarization & classification |
| 🧠 **Local LLM** | Ollama + llama3, data stays on-premise |
| 🔌 **Mock mode** | Test without real external services — ships with 10 demo tickets |
| ⚡ **Two run modes** | Async (background) and Sync (wait for results) |
| 🛡️ **Error resilience** | One failed ticket won't break the entire pipeline |
| 🔁 **Strict-JSON retries** | LLM responses are validated against a pydantic schema; the call is retried up to `LLM_MAX_RETRIES` times if the model returns malformed JSON |
| 📋 **REST API** | FastAPI + auto-generated Swagger UI documentation |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI  /run  /run/sync                  │
│                PipelineOrchestrator (app/main.py)            │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
           ▼                                  ▼
   ┌───────────────┐                ┌──────────────────┐
   │  JiraClient   │                │    LLMClient     │
   │               │                │                  │
   │ get_tickets() │                │summarize_ticket()│
   └──────┬────────┘                └────────┬─────────┘
          │                                  │
          ▼                                  ▼
   ┌─────────────┐                  ┌──────────────────┐
   │  Jira API   │                  │   Ollama API     │
   │  (on-prem)  │                  │ /api/generate    │
   └─────────────┘                  └──────────────────┘
```

### Data Model

```python
@dataclass
class JiraTicket:
    key:         str           # "PROJ-42"
    summary:     str           # Task title
    description: str           # Full description
    status:      str           # In Progress / To Do / ...
    assignee:    Optional[str] # Who is responsible
    priority:    Optional[str] # Critical / Medium / ...
    reporter:    Optional[str] # Who created
```

---

## 🚀 Quick Start (Docker)

The whole project runs in Docker — you don't need Python, Ollama, or anything else installed. Just Docker.

### 1. Check whether Docker is installed

Open a terminal and run:

```bash
docker --version
docker compose version
```

If both commands print a version — skip to **step 3**.
If you get "command not found" — go to **step 2**.

### 2. Install Docker

Download and install **Docker Desktop** for your OS:

- **Windows / macOS:** https://www.docker.com/products/docker-desktop/
- **Linux (Ubuntu/Debian):**
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER
  newgrp docker
  ```

After installation **launch Docker Desktop** (Windows/macOS) and wait until it shows "Docker is running". Then re-run the check from step 1.

### 3. Clone the project

```bash
git clone https://git.tech-on-air.com/atarasov/ai-integration.git
cd ai-integration
```

### 4. Create the configuration file

```bash
cp .env.example .env
```

By default the project runs in **mock mode** — it doesn't need real Jira tokens and works out of the box. If you want to connect to a real Jira, open `.env` in any text editor and fill in `JIRA_BASE_URL`, `JIRA_API_TOKEN` (optionally `JIRA_JQL` to override the default query), then set `JIRA_USE_MOCK=false`.

### 5. Build and start everything

```bash
docker compose up -d --build
```

The first build downloads images and pulls dependencies — it takes 2-5 minutes. Subsequent starts are instant.

### 6. Download the LLM model (one-time, ~4.9 GB)

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

This is needed only once. The model is stored in a Docker volume and survives restarts.

### 7. Open the service

- API:        http://localhost:8000
- Swagger UI: http://localhost:8000/docs

Done — the project is running.

---

### Useful commands

```bash
docker compose logs -f app      # watch app logs in real time
docker compose ps               # show running containers
docker compose restart app      # restart the app (e.g. after .env edit)
docker compose down             # stop everything (data preserved)
docker compose down -v          # stop everything AND wipe the LLM model
```

---

## 📡 API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Healthcheck |
| `POST` | `/run` | Run pipeline **asynchronously** (returns 200 immediately, processing runs in background) |
| `POST` | `/run/sync` | Run pipeline **synchronously** — waits and returns results |
| `POST` | `/tickets/process` | Accept one Jira ticket JSON, return the LLM summary + label |
| `POST` | `/tickets/process/batch` | Same as `/tickets/process`, batched. Failed tickets are skipped |
| `POST` | `/chat/message` | Receive a Rocket.Chat message forwarded by `ticket_router_api`; if the LLM detects an explicit self-assignment request, post a confirmation back to Rocket.Chat |
| `GET` | `/docs` | Swagger UI |

### Example Usage

```bash
# Async run
curl -X POST http://localhost:8000/run

# Sync run — returns JSON with results for each ticket
curl -X POST http://localhost:8000/run/sync

# Process one Jira ticket directly — returns the summary + label
curl -X POST http://localhost:8000/tickets/process \
  -H "Content-Type: application/json" \
  -d '{
    "key": "PROJ-42",
    "summary": "Authorization service crashing in prod",
    "description": "After deploying v2.3.1, users cannot log in. Error 503 in logs.",
    "status": "In Progress",
    "assignee": "Ivan Petrov",
    "priority": "Critical",
    "reporter": "Maria Sidorova"
  }'
```

### Example `/run/sync` Response

```json
[
  {
    "ticket": "PROJ-42",
    "status": "ok",
    "summary": "Authorization service refactoring task assigned to Ivan...",
    "label": "Product"
  },
  {
    "ticket": "PROJ-43",
    "status": "ok",
    "summary": "Critical bug in payment module. High priority...",
    "label": "complaint"
  }
]
```

---

## 🧪 Testing Without Real Services

By default, the service runs in **mock mode** for Jira. It doesn't connect to external systems and ships with **10 demo Jira tickets** covering different priorities, statuses, and label categories (complaint, pricing, spam, product, quality, etc.). This lets you start the project and see the pipeline work end-to-end without any credentials.

```env
JIRA_USE_MOCK=true
```

Switch it to `false` in `.env` for production mode, then make sure real URLs and tokens are filled in.

## 🔁 Strict-JSON Retries

LLM responses are validated against a pydantic schema (`LlmTicketSummary` for summaries). The LLM must additionally pick a `label` from the project's allowed list (loaded from `app/data/jira_labels.json`, exported via `scripts/export_jira_labels.py`); a label outside that list is treated as a validation failure. If parsing fails, the call is retried up to `LLM_MAX_RETRIES` extra times — by default `10`, so 11 attempts total. After the budget is exhausted the last error is re-raised and the surrounding endpoint returns 500; the caller decides whether to retry the request itself.

```env
LLM_MAX_RETRIES=10   # extra retries after the first attempt
```

---

## 📁 Project Structure

```
aiIntegration/
├── app/
│   ├── main.py            # FastAPI application, endpoints, pipeline orchestration
│   ├── core/
│   │   └── config.py      # Settings from .env (python-dotenv)
│   ├── models/
│   │   ├── ticket.py      # JiraTicket dataclass + payloads
│   │   └── summary.py     # LLM summary and response contracts
│   └── services/
│       ├── jira_client.py       # Fetching tickets from Jira
│       └── llm_client.py        # Summarization via Ollama
├── assets/
│   └── favicon.ico       # Browser icon served by FastAPI
├── docs/
│   ├── OLLAMA_SETUP.md       # Local LLM setup notes
│   └── diagrams/             # Draw.io / Excalidraw diagrams
├── scripts/
│   └── ensure_ollama.sh   # Local Ollama bootstrap helper
├── Dockerfile             # App container image definition
├── docker-compose.yml     # Two-service stack (app + ollama)
├── .dockerignore          # Files excluded from the image build
├── .env.example           # Environment variables template
└── requirements.txt       # Dependencies
```

---

## 🔧 Dependencies

```
fastapi==0.115.0      # Web framework
uvicorn==0.30.6       # ASGI server
requests==2.32.3      # HTTP client
python-dotenv==1.0.1  # .env file loader
```

---
