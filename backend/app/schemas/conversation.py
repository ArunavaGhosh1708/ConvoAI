from datetime import datetime

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list | None = None
    confidence: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    user_id: str
    channel: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_score: float | None = None
    messages: list[MessageOut] = []

    model_config = {"from_attributes": True}
