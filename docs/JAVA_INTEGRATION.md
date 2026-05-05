# ticket_router_api ↔ aiIntegration — Integration Guide

This document describes how `ticket_router_api` (Java/Spring Boot) should talk to `aiIntegration` (Python/FastAPI) and what changes are recommended on the Java side. The Python service has already been adjusted to expose the contracts described below.

## Roles

| Concern | Owner |
|---|---|
| Polling Jira for new tickets | **Java** (`TicketPollingScheduler`) |
| Picking the assignee with confidence | **Python** (`POST /analyze`) |
| Auto-assigning a ticket in Jira | **Java** (`JiraClient.assignTicket`) |
| Posting a notification to Rocket.Chat | **Java** (`RocketChatClient.sendTicketNotification`) |
| Classifying a Rocket.Chat reply (recommended) | **Python** (`POST /replies/process`) |
| Reply webhook entry point | **Java** (`RocketChatWebhookController`) |

> **One-way rule:** in the routing flow Python never calls Jira and never posts to Rocket.Chat. The Java side stays in charge of every side effect on external systems. The standalone Python pipeline (`/run`, `/run/sync`, `/tickets/process`) is for use **without** the Java router.

## Configuration on the Java side

`AI_SERVICE_BASE_URL` must point to the aiIntegration root, e.g. `http://aiintegration:8000`. No path suffix.

`ai.confidence-threshold` in `application.yml` decides when Java auto-assigns vs escalates. `0.8` is a good default; lower it (≈ `0.7`) once you trust the routing in your environment.

## Endpoint contracts

### `POST /analyze` — assignee routing

The existing `AiClient.analyze(...)` already matches this contract. **No changes needed in Java**, but verify these field names if you ever regenerate models:

Request (Java sends, Python receives):

```json
{
  "ticketId": "10001",
  "ticketKey": "PROJ-42",
  "summary": "Authorization service crashing in prod",
  "description": "After deploying v2.3.1, users cannot log in.",
  "priority": "Critical"
}
```

Response (Python sends, Java receives):

```json
{
  "assigneeAccountId": "ivan-petrov",
  "assigneeDisplayName": "Ivan Petrov",
  "confidence": 0.87,
  "reasoning": "Auth/backend incident in production matches Ivan's skills."
}
```

Notes:

- When the LLM cannot pick a candidate, both `assigneeAccountId` and `assigneeDisplayName` are `null` and `confidence` is below threshold — `TicketWorkflowService` falls back to Rocket.Chat.
- The `accountId` field of `AiAnalysisResponse` carries **the unique user identifier Jira expects**: the `name` (username) on Jira Server / Data Center, or the real `accountId` on Jira Cloud. Configure your `team_roster.json` accordingly. The `displayName` is informational only and must not be passed to the assignee endpoint.
- On any HTTP error from `/analyze`, the Python side returns `200 OK` with `confidence=0.0` and a `reasoning` that explains the LLM failure. The existing `AiServiceException` catch is still useful for transport errors (timeouts, 5xx).

### `POST /replies/process` — reply classification (recommended adoption)

Today `RocketChatWebhookController` parses `take TICKET-KEY` with a regex. That misses everything else: "I'll take it", "yes I'm on it", "not me, ask Maria", "need prod logs first". Routing the text through Python adds nuance:

Request (Java would send):

```json
{
  "ticket_key": "PROJ-42",
  "source_message_id": "rocket-msg-123",
  "parent_message_id": "rocket-parent-001",
  "source_user_id": "user-42",
  "source_username": "ivan.petrov",
  "text": "I cannot take it yet, I need production logs."
}
```

Response (Python returns):

```json
{
  "source_message_id": "rocket-msg-123",
  "source_user_id": "user-42",
  "confirmed_to_take": false,
  "clarification_response": "Needs production logs before taking the ticket."
}
```

Java-side recommendations:

1. **Persist outbound bot messages.** When `RocketChatClient.sendTicketNotification` posts a message, store `(ticketKey, rocketChatMessageId, channel)` so an inbound reply can be correlated back to the ticket. Without this, the webhook only sees "user X sent text Y in channel Z" and cannot recover `ticket_key` or `parent_message_id`.
2. **In `RocketChatWebhookController`,** keep the cheap `take TICKET-KEY` fast path for explicit confirmations, but for any other text in a tracked thread call `POST /replies/process` and act on the response:
   - `confirmed_to_take == true` → call `JiraClient.assignTicket` and post a confirmation message.
   - `confirmed_to_take == false` → post `clarification_response` back into the thread; do **not** assign.
3. The webhook payload `RocketChatWebhookPayload` is missing `message_id` and `thread_id`. Add them as `@JsonProperty("message_id")` / `@JsonProperty("tmid")` fields so you can correlate replies to outbound bot messages.

## Java code recommendations

### Already applied in `ticket_router_api`

1. **`TicketWorkflowService.autoAssign` now passes `assigneeAccountId`** instead of `assigneeDisplayName`, and skips auto-assign with an escalation to Rocket.Chat when `accountId` is missing.
2. **`AiClient.analyze` has a 120 s timeout** on `.block(...)` so a stuck Ollama cannot freeze the scheduler thread.
3. **`TicketPollingScheduler` wraps the per-ticket call in try/catch** so one bad ticket does not abort the batch.
4. **`TicketPollingScheduler` persists `lastPolledAt`** to `poll-state.txt` (path overridable via `JIRA_POLL_STATE_FILE`) and reloads it on startup, so tickets created during downtime are not lost.
5. **`RocketChatWebhookController` checks `X-Webhook-Token`** against `rocketchat.webhook-secret`. Configure on the Rocket.Chat outgoing-integration side; leave empty in dev to disable.

### Still pending (good follow-ups)

1. **Idempotency.** `process` does not deduplicate. A flaky run that re-fetches the same tickets will re-assign and re-post to chat. Track processed `ticketKey` values (a bounded LRU is enough for a single instance) and skip duplicates.
2. **`@Scheduled` runs on the default single-threaded scheduler.** If `pollNewTickets` overruns the interval, ticks stack up. Configure a `TaskScheduler` bean with an explicit pool size, or guard with `@Async`.
3. **Webhook payload is missing thread context.** `RocketChatWebhookPayload` has no `message_id` or `tmid` — needed to correlate replies back to outbound bot messages and to feed `/replies/process`. Add `@JsonProperty("message_id")` and `@JsonProperty("tmid")` fields, and persist outbound `messageId` when posting to Rocket.Chat.
4. **`/replies/process` is not yet wired.** The webhook today only handles the explicit `take TICKET-KEY` fast path. For free-form replies, route through Python — see the next section.

## Sequence diagram (routing flow)

```
Scheduler  →  Java JiraClient        : fetchNewTicketsSince(lastPolledAt)
Scheduler  →  Java TicketWorkflow    : process(ticket)
Workflow   →  Python  POST /analyze  : { ticketKey, summary, description, priority }
Python     →  Ollama                 : LLM prompt + team roster
Python     →  Workflow               : { assigneeAccountId, confidence, reasoning }

[confidence >= threshold]
  Workflow →  Jira  PUT /issue/{key}/assignee   (auto-assign)

[confidence <  threshold]
  Workflow →  RocketChat  POST /chat.postMessage   (escalate, mention reasoning)
              ↓
              user replies
              ↓
  Webhook  →  Python  POST /replies/process    (recommended)
  Webhook  →  Jira    PUT /issue/{key}/assignee  (if confirmed_to_take)
  Webhook  →  RocketChat  POST /chat.postMessage  (if clarification needed)
```

## What stays standalone in Python

`POST /run`, `POST /run/sync`, `POST /tickets/process` and `POST /tickets/process/batch` still pull from Jira and post to Rocket.Chat directly. **Do not call them from Java** — they would duplicate the side effects the router already owns. They exist so the Python service can be used on its own without the router.
