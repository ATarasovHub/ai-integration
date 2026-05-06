from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Internal data object that represents one Rocket.Chat reply.
@dataclass
class RocketChatReply:
    ticket_key: str
    source_message_id: str
    parent_message_id: str
    source_user_id: str
    source_username: Optional[str]
    text: str


# API input model for incoming Rocket.Chat replies.
class RocketChatReplyPayload(BaseModel):
    ticket_key: str = Field(..., examples=["PROJ-42"])
    source_message_id: str = Field(..., examples=["rocket-msg-123"])
    parent_message_id: str = Field(
        ...,
        examples=["rocket-parent-msg-456"],
        description="ID of the original bot message or thread root this reply belongs to.",
    )
    source_user_id: str = Field(..., examples=["user-42"])
    source_username: Optional[str] = Field(default=None, examples=["ivan.petrov"])
    text: str = Field(..., min_length=1, examples=["I cannot take it yet, I need production logs."])

    # Convert the API model into the internal domain object.
    def to_domain(self) -> RocketChatReply:
        return RocketChatReply(
            ticket_key=self.ticket_key,
            source_message_id=self.source_message_id,
            parent_message_id=self.parent_message_id,
            source_user_id=self.source_user_id,
            source_username=self.source_username,
            text=self.text,
        )


# Result of the AI classification: ticket accepted or clarification needed.
class ReplyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_message_id: str
    source_user_id: str
    confirmed_to_take: bool
    clarification_response: Optional[str] = None

    # Validation: clarification is required only when the ticket is not accepted.
    @model_validator(mode="after")
    def validate_clarification_response(self):
        if self.confirmed_to_take:
            self.clarification_response = None
        elif not self.clarification_response:
            raise ValueError(
                "clarification_response must be provided when confirmed_to_take is false"
            )
        return self
