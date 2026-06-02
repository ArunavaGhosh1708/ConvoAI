from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Client-generated session UUID")
    message: str = Field(..., min_length=1, max_length=4096)
    channel: Literal["chat", "voice"] = "chat"
    stream: bool = Field(True, description="If true, response is SSE; if false, returns JSON")


class SourceChunk(BaseModel):
    chunk_id: str
    document_id: str
    content_preview: str
    similarity: float


class EscalationPayload(BaseModel):
    conversation_id: str
    session_id: str
    channel: str
    escalation_reason: str
    prior_turns: list[dict]
    retrieved_sources: list[dict]
    escalated_at: str


class ChatResponse(BaseModel):
    """Returned when stream=false."""
    session_id: str
    conversation_id: str
    response: str
    sources: list[SourceChunk]
    confidence: float
    escalated: bool
    escalation_payload: EscalationPayload | None = None


# SSE event payload models (serialised to JSON in the data: field)

class TokenEvent(BaseModel):
    token: str


class SourcesEvent(BaseModel):
    chunks: list[SourceChunk]


class DoneEvent(BaseModel):
    session_id: str
    conversation_id: str
    confidence: float
    escalated: bool
    escalation_payload: EscalationPayload | None = None
