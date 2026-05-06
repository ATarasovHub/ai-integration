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

**aiIntegration** is the AI brain for ticket processing. It serves two roles:

1. **Standalone pipeline** — pulls open tickets from Jira, summarizes each via a local LLM (Ollama), and forwards the summaries to `ticket_router_api`, which posts them to Rocket.Chat.
2. **AI service for `ticket_router_api`** — exposes ticket summarization endpoints and `POST /replies/process` for reply classification.

**aiIntegration never talks to Rocket.Chat directly.** All Rocket.Chat delivery is owned by the Java router; aiIntegration only runs LLM logic and forwards ready-to-post payloads.

> **Fully on-premise:** data never leaves your infrastructure. Jira, Rocket.Chat, and LLM — everything runs locally.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🔄 **3-stage pipeline** | Jira → LLM summarization → ticket_router_api → Rocket.Chat |
| 🧠 **Local LLM** | Ollama + llama3, data stays on-premise |
| 🔌 **Mock mode** | Test without real external services |
| ⚡ **Two run modes** | Async (background) and Sync (wait for results) |
| 🛡️ **Error resilience** | One failed ticket won't break the entire pipeline |
| 📋 **REST API** | FastAPI + auto-generated Swagger UI documentation |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI  /run  /run/sync                  │
│                PipelineOrchestrator (app/main.py)            │
└──────────┬──────────────────────┬───────────────────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
   ┌───────────────┐    ┌──────────────────┐   ┌──────────────────┐
   │  JiraClient   │    │    LLMClient     │   │  RouterClient    │
   │               │    │                  │   │                  │
   │ get_tickets() │    │summarize_ticket()│   │ send_to_router() │
   └──────┬────────┘    └────────┬─────────┘   └────────┬─────────┘
          │                      │                       │
          ▼                      ▼                       ▼
   ┌─────────────┐    ┌──────────────────┐   ┌──────────────────────┐
   │  Jira API   │    │   Ollama API     │   │ ticket_router_api    │
   │  (on-prem)  │    │ /api/generate    │   │ /api/rocketchat/...  │
   └─────────────┘    └──────────────────┘   └──────────┬───────────┘
                                                        ▼
                                              ┌──────────────────┐
                                              │ Rocket.Chat API  │
                                              │/api/v1/chat.post │
                                              └──────────────────┘
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

## 🚀 Quick Start

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/your-username/aiIntegration.git
cd aiIntegration

python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Open .env and insert your tokens and URLs
```

<details>
<summary>📄 Environment Variables (.env.example)</summary>

```env
# Jira
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=MYPROJECT

# Ollama (local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# ticket_router_api (owns Rocket.Chat delivery)
TICKET_ROUTER_BASE_URL=http://localhost:8080/ticket-router-api
```

</details>

### 3. Start Ollama

```bash
ollama serve
ollama pull llama3    # Download the model if not already loaded
```

### 4. Start the Service

```bash
uvicorn app.main:app --reload --port 8000
```

Service available at `http://localhost:8000` · Documentation: `http://localhost:8000/docs`

---

## 📡 API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Healthcheck |
| `POST` | `/run` | Run pipeline **asynchronously** (returns 200 immediately, processing runs in background) |
| `POST` | `/run/sync` | Run pipeline **synchronously** — waits and returns results |
| `POST` | `/tickets/process` | Accept one Jira ticket JSON from `ticket_router_api`, return the LLM summary. Java posts to Rocket.Chat. |
| `POST` | `/tickets/process/batch` | Same as `/tickets/process`, batched. Does **not** post to Rocket.Chat. |
| `POST` | `/replies/process` | Accept one Rocket.Chat reply, classify whether the user takes the ticket |
| `GET` | `/docs` | Swagger UI |

### Example Usage

```bash
# Async run
curl -X POST http://localhost:8000/run

# Sync run — returns JSON with results for each ticket
curl -X POST http://localhost:8000/run/sync

# Process one Jira ticket directly — returns the summary, does not post to Rocket.Chat
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

# Process one Rocket.Chat reply and preserve message/user correlation
curl -X POST http://localhost:8000/replies/process \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_key": "PROJ-42",
    "source_message_id": "rocket-msg-123",
    "parent_message_id": "rocket-parent-001",
    "source_user_id": "user-42",
    "source_username": "ivan.petrov",
    "text": "I cannot take it yet, I need production logs."
  }'
```

### Example `/run/sync` Response

```json
[
  {
    "ticket": "PROJ-42",
    "status": "ok",
    "summary": "Authorization service refactoring task assigned to Ivan..."
  },
  {
    "ticket": "PROJ-43",
    "status": "ok",
    "summary": "Critical bug in payment module. High priority..."
  }
]
```

---

## 🧪 Testing Without Real Services

By default, the service runs in **mock mode** for Jira and the router. It doesn't connect to external systems, uses test data for Jira, and logs the would-be router payload to console instead of forwarding it.

```env
JIRA_USE_MOCK=true
TICKET_ROUTER_USE_MOCK=true
```

Switch them to `false` in `.env` for production mode, then make sure real URLs and tokens are filled in.

## 💬 Reply Classification Flow

The service can also classify a Rocket.Chat reply for one concrete message and user. This avoids mixing replies when several people answer while the LLM is still processing.

The classifier returns:

```json
{
  "source_message_id": "rocket-msg-123",
  "source_user_id": "user-42",
  "confirmed_to_take": false,
  "clarification_response": "Needs production logs before taking the ticket."
}
```

Recommended next step for production: persist outbound bot messages, inbound replies, and LLM decisions in a database so the service can safely deduplicate and aggregate multiple replies in one thread.

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
│   │   ├── summary.py     # LLM summary and Rocket.Chat message contracts
│   │   └── reply.py       # Rocket.Chat reply payloads + decision
│   └── services/
│       ├── jira_client.py       # Fetching tickets from Jira (standalone mode)
│       ├── llm_client.py        # Summarization via Ollama
│       ├── reply_classifier.py  # Classifying Rocket.Chat replies via Ollama
│       ├── rocketchat_client.py # Formatting Rocket.Chat message text
│       └── router_client.py     # Forwarding ready-to-post payloads to ticket_router_api
├── assets/
│   └── favicon.ico       # Browser icon served by FastAPI
├── docs/
│   ├── JAVA_INTEGRATION.md   # Recommendations for the ticket_router_api side
│   ├── JAVA_TODO.md          # Java-side follow-up checklist
│   ├── OLLAMA_SETUP.md       # Local LLM setup notes
│   └── diagrams/             # Draw.io / Excalidraw diagrams
├── scripts/
│   └── ensure_ollama.sh   # Local Ollama bootstrap helper
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
