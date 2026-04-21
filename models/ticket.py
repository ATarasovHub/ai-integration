from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


# Internes Datenobjekt – repräsentiert ein einzelnes Jira-Ticket
@dataclass
class JiraTicket:
    key: str
    summary: str
    description: str
    status: str
    assignee: Optional[str] = None
    priority: Optional[str] = None
    reporter: Optional[str] = None


# API-Eingabemodell mit Validierung – wird vom Endpunkt empfangen
class JiraTicketPayload(BaseModel):
    key: str = Field(..., examples=["PROJ-42"])
    summary: str
    description: str = "No description available"
    status: str = "Unknown"
    assignee: Optional[str] = None
    priority: Optional[str] = None
    reporter: Optional[str] = None

    # Konvertiert das API-Modell in das interne Domänenobjekt
    def to_domain(self) -> JiraTicket:
        return JiraTicket(
            key=self.key,
            summary=self.summary,
            description=self.description,
            status=self.status,
            assignee=self.assignee,
            priority=self.priority,
            reporter=self.reporter,
        )


# Eingabemodell für die Stapelverarbeitung mehrerer Tickets
class JiraTicketsBatchPayload(BaseModel):
    tickets: list[JiraTicketPayload]
