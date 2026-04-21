import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse

from jira_client import get_tickets
from llm_client import summarize_ticket
from reply_classifier import classify_reply
from models.reply import RocketChatReplyPayload
from models.ticket import JiraTicket, JiraTicketPayload, JiraTicketsBatchPayload
from rocketchat_client import send_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jira → LLM → Rocket.Chat Bot",
    description="Fetches tickets from Jira, summarizes via Ollama, sends to Rocket.Chat",
    version="1.0.0"
)


def process_ticket(ticket: JiraTicket) -> dict:
    """Summarize one ticket and send the result to Rocket.Chat."""
    logger.info(f"Processing ticket: {ticket.key}")
    summary = summarize_ticket(ticket)
    send_summary(ticket, summary)
    logger.info(f"Ticket {ticket.key} successfully processed and sent.")
    return {"ticket": ticket.key, "status": "ok", "summary": summary}


async def process_tickets_pipeline():
    """Main ticket processing pipeline."""
    logger.info("Starting ticket processing pipeline...")

    # 1. Fetch tickets from Jira
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


@app.post("/tickets/process", tags=["Pipeline"])
async def process_ticket_from_payload(ticket: JiraTicketPayload):
    """Accept Jira ticket payload directly, summarize it, and send to Rocket.Chat."""
    try:
        result = process_ticket(ticket.to_domain())
        return JSONResponse({"status": "done", "result": result})
    except Exception as e:
        logger.error(f"Error processing inbound ticket {ticket.key}: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "ticket": ticket.key, "detail": str(e)},
        )


@app.post("/tickets/process/batch", tags=["Pipeline"])
async def process_tickets_batch(payload: JiraTicketsBatchPayload):
    """Accept a batch of Jira tickets and process them sequentially."""
    results = []

    for ticket_payload in payload.tickets:
        try:
            results.append(process_ticket(ticket_payload.to_domain()))
        except Exception as e:
            logger.error(f"Error processing inbound ticket {ticket_payload.key}: {e}")
            results.append(
                {
                    "ticket": ticket_payload.key,
                    "status": "error",
                    "detail": str(e),
                }
            )

    return JSONResponse({"status": "done", "results": results})


@app.post("/replies/process", tags=["Replies"])
async def process_reply(payload: RocketChatReplyPayload):
    """Classify one Rocket.Chat reply and keep the original message/user correlation."""
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
