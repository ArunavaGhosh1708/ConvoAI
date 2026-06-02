from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EscalationTicketOut(BaseModel):
    id: str
    conversation_id: str
    session_id: str
    reason: str
    status: Literal["open", "in_progress", "resolved"]
    context_chunks: dict | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class EscalationTicketPatch(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
