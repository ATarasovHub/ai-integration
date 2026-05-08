import logging
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.models.chat import RocketChatMessagePayload
from app.models.summary import TicketSummaryResponse
from app.models.ticket import JiraTicketPayload, JiraTicketsBatchPayload
from app.services.jira_client import get_tickets
from app.services.llm_client import generate_chat_reply, summarize_ticket
from app.services.ticket_router_client import send_rocket_message

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jira → LLM Bot",
    description="Fetches tickets from Jira and summarizes them via Ollama",
    version="1.0.0"
)


def summarize_only(ticket):
    logger.info(f"Summarizing ticket: {ticket.key}")
    result = summarize_ticket(ticket)
    return TicketSummaryResponse(ticket=ticket.key, summary=result.summary, label=result.label)


def process_ticket(ticket):
    logger.info(f"Processing ticket: {ticket.key}")
    result = summarize_ticket(ticket)
    logger.info(f"Ticket {ticket.key} summarized successfully.")
    return {"ticket": ticket.key, "status": "ok", "summary": result.summary, "label": result.label}


async def process_tickets_pipeline():
    logger.info("Starting ticket processing pipeline...")

    tickets = get_tickets()
    if not tickets:
        logger.warning("No tickets found or Jira is unavailable.")
        return {"status": "no_tickets"}

    logger.info(f"Received tickets: {len(tickets)}")
    results = []

    for ticket in tickets:
        try:
            results.append(process_ticket(ticket))
        except Exception as e:
            logger.error(f"Error processing ticket {ticket.key}: {e}")
            results.append({"ticket": ticket.key, "status": "error", "detail": str(e)})

    return results


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon_path = ASSETS_DIR / "favicon.ico"
    if not icon_path.exists():
        raise HTTPException(status_code=404, detail="favicon not found")
    return FileResponse(icon_path)


@app.get("/", tags=["Health"])
def root():
    return {"status": "running", "service": "Jira LLM Bot"}


@app.post("/run", tags=["Pipeline"])
async def run_pipeline(background_tasks: BackgroundTasks):
    background_tasks.add_task(process_tickets_pipeline)
    return {"status": "started", "message": "Pipeline started in background"}


@app.post("/run/sync", tags=["Pipeline"])
async def run_pipeline_sync():
    result = await process_tickets_pipeline()
    return {"status": "done", "results": result}


@app.post("/tickets/process", tags=["Pipeline"], response_model=TicketSummaryResponse)
async def process_ticket_from_payload(ticket: JiraTicketPayload):
    try:
        return summarize_only(ticket.to_domain())
    except Exception as e:
        logger.error(f"Error processing inbound ticket {ticket.key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/message", tags=["Chat"])
async def receive_chat_message(payload: RocketChatMessagePayload):
    logger.info(
        f"Received Rocket.Chat message from {payload.user_name}, "
        f"ticketKey={payload.ticket_key}, threadMessageId={payload.thread_message_id}"
    )

    if not payload.ticket_key:
        logger.info("No ticketKey resolved for the message, skipping LLM decision")
        return {"status": "skipped", "reason": "no_ticket_key"}

    try:
        decision = generate_chat_reply(payload)
    except Exception as e:
        logger.error(f"Error generating chat reply for {payload.ticket_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    try:
        send_rocket_message(payload.ticket_key, decision.message)
    except Exception as e:
        logger.error(f"Error sending Rocket.Chat message for {payload.ticket_key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "assigned": decision.assign, "message": decision.message}


@app.post("/tickets/process/batch", tags=["Pipeline"], response_model=list[TicketSummaryResponse])
async def process_tickets_batch(payload: JiraTicketsBatchPayload):
    results = []

    for ticket_payload in payload.tickets:
        try:
            results.append(summarize_only(ticket_payload.to_domain()))
        except Exception as e:
            logger.error(f"Error processing inbound ticket {ticket_payload.key}: {e}")

    return results
