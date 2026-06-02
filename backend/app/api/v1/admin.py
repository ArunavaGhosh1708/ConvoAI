"""GET /api/v1/admin/metrics — live dashboard metrics."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin_jwt
from app.models.conversation import Conversation
from app.schemas.admin import MetricsResponse

router = APIRouter(tags=["admin"])


@router.get("/admin/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> MetricsResponse:
    total     = await db.scalar(select(func.count(Conversation.id))) or 0
    active    = await db.scalar(select(func.count(Conversation.id)).where(Conversation.status == "active"))    or 0
    resolved  = await db.scalar(select(func.count(Conversation.id)).where(Conversation.status == "resolved"))  or 0
    escalated = await db.scalar(select(func.count(Conversation.id)).where(Conversation.status == "escalated")) or 0
    avg_conf  = await db.scalar(
        select(func.avg(Conversation.resolution_score)).where(Conversation.resolution_score.isnot(None))
    )

    resolution_rate = (resolved  / total * 100) if total else 0.0
    escalation_rate = (escalated / total * 100) if total else 0.0

    return MetricsResponse(
        total_sessions=total,
        active_sessions=active,
        resolution_rate=round(resolution_rate, 2),
        escalation_rate=round(escalation_rate, 2),
        avg_confidence=round(float(avg_conf), 4) if avg_conf is not None else 0.0,
        refreshed_at=datetime.now(timezone.utc).isoformat(),
    )
