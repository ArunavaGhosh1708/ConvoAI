"""
GET /api/v1/admin/review-queue

Returns conversations that:
  - are not already escalated
  - have at least one assistant message with a confidence score
  - whose average assistant confidence is below the configured threshold

This is FR-24: "flag low-confidence sessions for manual review."
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import require_admin_jwt
from app.models.conversation import Conversation, Message

router = APIRouter(tags=["admin"])


class ReviewQueueItem(BaseModel):
    conversation_id: str
    user_id: str
    channel: str
    avg_confidence: float
    message_count: int
    created_at: str


@router.get("/admin/review-queue", response_model=list[ReviewQueueItem])
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> list[ReviewQueueItem]:
    """
    Conversations below the escalation confidence threshold that have not
    yet been escalated — candidates for human review.
    """
    threshold = settings.escalation_confidence_threshold

    avg_conf = func.avg(Message.confidence).label("avg_confidence")
    msg_count = func.count(Message.id).label("message_count")

    stmt = (
        select(
            Conversation.id,
            Conversation.user_id,
            Conversation.channel,
            Conversation.created_at,
            avg_conf,
            msg_count,
        )
        .join(Message, Message.conversation_id == Conversation.id)
        .where(
            Conversation.status != "escalated",
            Message.role == "assistant",
            Message.confidence.isnot(None),
        )
        .group_by(
            Conversation.id,
            Conversation.user_id,
            Conversation.channel,
            Conversation.created_at,
        )
        .having(func.avg(Message.confidence) < threshold)
        .order_by(avg_conf.asc())
    )

    rows = (await db.execute(stmt)).all()
    return [
        ReviewQueueItem(
            conversation_id=str(row.id),
            user_id=row.user_id,
            channel=row.channel,
            avg_confidence=round(float(row.avg_confidence), 4),
            message_count=row.message_count,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
