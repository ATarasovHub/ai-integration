from pydantic import BaseModel, ConfigDict, Field


# Strict contract that the LLM must produce. Ollama is also called with format="json",
# so the model is constrained to valid JSON; this class enforces the shape on our side.
class LlmTicketSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    label: str


# Rocket.Chat-ready payload returned by /tickets/process and /tickets/process/batch.
# ticket_router_api appends `channel` and auth headers, then POSTs to /api/v1/chat.postMessage.
class RocketChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticketKey: str = Field(..., examples=["PROJ-42"])
    text: str
