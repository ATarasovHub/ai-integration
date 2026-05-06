from app.models.summary import LlmTicketSummary
from app.models.ticket import JiraTicket


def format_message(ticket: JiraTicket, result: LlmTicketSummary) -> str:
    # Build the final Rocket.Chat message text from ticket data and the AI summary.
    return (
        f"📋 *Ticket {ticket.key}* | {ticket.status} | 🔥 {ticket.priority or 'N/A'}\n"
        f"*{ticket.summary}*\n\n"
        f"{result.summary}\n\n"
        f"🏷 Label: {result.label}\n"
        f"👤 Assignee: {ticket.assignee or 'Not assigned'}"
    )
