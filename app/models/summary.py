from pydantic import BaseModel, ConfigDict, Field


# Strict contract that the LLM must produce. Ollama is also called with format="json",
# so the model is constrained to valid JSON; this class enforces the shape on our side.
class LlmTicketSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    label: str


# Response payload returned by /tickets/process and /tickets/process/batch.
class TicketSummaryResponse(BaseModel):
    ticket: str = Field(..., examples=["PROJ-42"])
    summary: str
    label: str
