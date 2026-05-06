import logging
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse

# Import clients, classifiers, and data models used by the API routes.
from app.models.reply import RocketChatReplyPayload
from app.models.summary import RocketChatMessage
from app.models.ticket import JiraTicket, JiraTicketPayload, JiraTicketsBatchPayload
from app.services.jira_client import get_tickets
from app.services.llm_client import summarize_ticket
from app.services.reply_classifier import classify_reply
from app.services.rocketchat_client import format_message
from app.services.router_client import send_to_router

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"

# Configure application logging for all modules.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Create the FastAPI application with metadata for the Swagger UI.
app = FastAPI(
    title="Jira → LLM → Rocket.Chat Bot",
    description="Fetches tickets from Jira, summarizes via Ollama, sends to Rocket.Chat",
    version="1.0.0"
)


def summarize_only(ticket: JiraTicket) -> RocketChatMessage:
    """Summarize one ticket and return a Rocket.Chat-ready payload for ticket_router_api."""
    # Java appends `channel` and auth headers, then forwards `text` to /api/v1/chat.postMessage.
    logger.info(f"Summarizing ticket: {ticket.key}")
    summary = summarize_ticket(ticket)
    return RocketChatMessage(ticketKey=ticket.key, text=format_message(ticket, summary))


def process_ticket(ticket: JiraTicket) -> dict:
    """Standalone pipeline: summarize one ticket and forward the result to ticket_router_api."""
    # Used only by /run and /run/sync. Posting to Rocket.Chat is owned by the Java router.
    logger.info(f"Processing ticket: {ticket.key}")
    summary = summarize_ticket(ticket)
    send_to_router(RocketChatMessage(ticketKey=ticket.key, text=format_message(ticket, summary)))
    logger.info(f"Ticket {ticket.key} successfully processed and forwarded.")
    return {"ticket": ticket.key, "status": "ok", "summary": summary}

async def process_tickets_pipeline():
    """Main ticket processing pipeline."""
    logger.info("Starting ticket processing pipeline...")

    # Load open Jira tickets from the configured source.
    tickets = get_tickets()
    if not tickets:
        logger.warning("No tickets found or Jira is unavailable.")
        return {"status": "no_tickets"}

    # Process each ticket separately so one error does not stop the full batch.
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
    # Return the browser icon without showing it in the API documentation.
    return FileResponse(ASSETS_DIR / "favicon.ico")


@app.get("/", tags=["Health"])
def root():
    # Simple health check endpoint to confirm that the service is running.
    return {"status": "running", "service": "Jira LLM Bot"}


@app.post("/run", tags=["Pipeline"])
async def run_pipeline(background_tasks: BackgroundTasks):
    """Run the ticket processing pipeline (async in background)."""
    # Start the pipeline in the background and return immediately.
    background_tasks.add_task(process_tickets_pipeline)
    return JSONResponse({"status": "started", "message": "Pipeline started in background"})


@app.post("/run/sync", tags=["Pipeline"])
async def run_pipeline_sync():
    """Run the pipeline synchronously and get results immediately."""
    # Run the full pipeline and wait until all results are ready.
    result = await process_tickets_pipeline()
    return JSONResponse({"status": "done", "results": result})


@app.post("/tickets/process", tags=["Pipeline"], response_model=RocketChatMessage)
async def process_ticket_from_payload(ticket: JiraTicketPayload):
    """Accept one Jira ticket from ticket_router_api and return a Rocket.Chat-ready JSON.

    Posting to Rocket.Chat is owned by the Java router — this endpoint never touches Rocket.Chat.
    """
    try:
        return summarize_only(ticket.to_domain())
    except Exception as e:
        logger.error(f"Error processing inbound ticket {ticket.key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tickets/process/batch", tags=["Pipeline"], response_model=list[RocketChatMessage])
async def process_tickets_batch(payload: JiraTicketsBatchPayload):
    """Accept a batch of Jira tickets and return Rocket.Chat-ready JSONs. No Rocket.Chat posting here."""
    # Failed tickets are skipped (and logged) so the response stays a uniform list of RocketChatMessage.
    results: list[RocketChatMessage] = []

    for ticket_payload in payload.tickets:
        try:
            results.append(summarize_only(ticket_payload.to_domain()))
        except Exception as e:
            logger.error(f"Error processing inbound ticket {ticket_payload.key}: {e}")

    return results


@app.post("/replies/process", tags=["Replies"])
async def process_reply(payload: RocketChatReplyPayload):
    """Classify one Rocket.Chat reply and keep the original message/user correlation."""
    # Send one Rocket.Chat reply to the classifier and return the decision.
    try:
        result = classify_reply(payload.to_domain())
        return JSONResponse({"status": "done", "result": result.model_dump()})
    except Exception as e:
        logging.error(
            "Error processing Rocket.Chat reply %s: %s",
            payload.source_message_id,
            e,
        )
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "source_message_id": payload.source_message_id,
                "detail": str(e),
            },
        )
