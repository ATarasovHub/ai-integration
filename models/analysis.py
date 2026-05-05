from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# Input model that matches the AiAnalysisRequest contract sent by ticket_router_api.
# Field names use camelCase on purpose so the Java side does not need a mapper.
class AiAnalysisRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticketId: Optional[str] = Field(default=None, examples=["10001"])
    ticketKey: str = Field(..., examples=["PROJ-42"])
    summary: str = Field(..., examples=["Authorization service crashing in prod"])
    description: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None, examples=["Critical"])


# Response model that matches the AiAnalysisResponse contract expected by ticket_router_api.
# confidence is what the Java side compares against ai.confidence-threshold for auto-assignment.
class AiAnalysisResponse(BaseModel):
    assigneeAccountId: Optional[str] = None
    assigneeDisplayName: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
