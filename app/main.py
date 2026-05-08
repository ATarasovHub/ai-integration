import logging
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.models.summary import TicketSummaryResponse
from app.models.ticket import JiraTicket, JiraTicketPayload, JiraTicketsBatchPayload
from app.services.jira_client import get_tickets
from app.services.llm_client import summarize_ticket

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


def summarize_only(ticket: JiraTicket) -> TicketSummaryResponse:
    """Summarize one ticket and return the structured result."""
    logger.info(f"Summarizing ticket: {ticket.key}")
    result = summarize_ticket(ticket)
    return TicketSummaryResponse(ticket=ticket.key, summary=result.summary, label=result.label)


def process_ticket(ticket: JiraTicket) -> dict:
    """Standalone pipeline step: summarize one ticket and return the result."""
    logger.info(f"Processing ticket: {ticket.key}")
    result = summarize_ticket(ticket)
    logger.info(f"Ticket {ticket.key} summarized successfully.")
    return {"ticket": ticket.key, "status": "ok", "summary": result.summary, "label": result.label}


async def process_tickets_pipeline():
    """Main ticket processing pipeline."""
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
    return FileResponse(ASSETS_DIR / "favicon.ico")


@app.get("/", tags=["Health"])
def root():
    return {"status": "running", "service": "Jira LLM Bot"}


@app.post("/run", tags=["Pipeline"])
async def run_pipeline(background_tasks: BackgroundTasks):
    """Run the ticket processing pipeline (async in background)."""
    background_tasks.add_task(process_tickets_pipeline)
    return JSONResponse({"status": "started", "message": "Pipeline started in background"})


@app.post("/run/sync", tags=["Pipeline"])
async def run_pipeline_sync():
    """Run the pipeline synchronously and get results immediately."""
    result = await process_tickets_pipeline()
    return JSONResponse({"status": "done", "results": result})


@app.post("/tickets/process", tags=["Pipeline"], response_model=TicketSummaryResponse)
async def process_ticket_from_payload(ticket: JiraTicketPayload):
    """Accept one Jira ticket and return its AI summary + label."""
    try:
        return summarize_only(ticket.to_domain())
    except Exception as e:
        logger.error(f"Error processing inbound ticket {ticket.key}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tickets/process/batch", tags=["Pipeline"], response_model=list[TicketSummaryResponse])
async def process_tickets_batch(payload: JiraTicketsBatchPayload):
    """Accept a batch of Jira tickets and return AI summaries. Failed tickets are skipped."""
    results: list[TicketSummaryResponse] = []

    for ticket_payload in payload.tickets:
        try:
            results.append(summarize_only(ticket_payload.to_domain()))
        except Exception as e:
            logger.error(f"Error processing inbound ticket {ticket_payload.key}: {e}")

    return results
