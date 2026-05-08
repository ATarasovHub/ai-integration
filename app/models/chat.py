from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RocketChatMessagePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_name: str = Field(..., alias="userName")
    text: str = ""
    thread_message_id: Optional[str] = Field(default=None, alias="threadMessageId")
    ticket_key: Optional[str] = Field(default=None, alias="ticketKey")


class LlmAssignmentDecision(BaseModel):
    assign: bool
    message: str = ""


class OutgoingRocketMessage(BaseModel):
    ticket_key: str = Field(..., serialization_alias="ticketKey")
    text: str
