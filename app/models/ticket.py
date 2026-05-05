from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


# Internal data object that represents one Jira ticket.
@dataclass
class JiraTicket:
    key: str
    summary: str
    description: str
    status: str
    assignee: Optional[str] = None
    priority: Optional[str] = None
    reporter: Optional[str] = None


# API input model with validation, received by the endpoint.
class JiraTicketPayload(BaseModel):
    key: str = Field(..., examples=["PROJ-42"])
    summary: str
    description: str = "No description available"
    status: str = "Unknown"
    assignee: Optional[str] = None
    priority: Optional[str] = None
    reporter: Optional[str] = None

    # Convert the API model into the internal domain object.
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


# Input model for batch processing multiple tickets.
class JiraTicketsBatchPayload(BaseModel):
    tickets: list[JiraTicketPayload]
