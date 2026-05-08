from pydantic import BaseModel, ConfigDict, Field


class LlmTicketSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    label: str


class TicketSummaryResponse(BaseModel):
    ticket: str = Field(..., examples=["PROJ-42"])
    summary: str
    label: str
