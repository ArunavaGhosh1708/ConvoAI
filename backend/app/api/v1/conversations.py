"""GET /api/v1/conversations/{id} and DELETE /api/v1/conversations/{id}."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import require_jwt
from app.models.conversation import Conversation, Message
from app.schemas.conversation import ConversationOut, MessageOut

router = APIRouter(tags=["conversations"])


def _to_str_id(obj_id) -> str:
    return str(obj_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_jwt),
) -> ConversationOut:
    """Return the full conversation transcript by conversation UUID."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID")

    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv_uuid)
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages_sorted = sorted(conv.messages, key=lambda m: m.created_at)

    return ConversationOut(
        id=_to_str_id(conv.id),
        user_id=conv.user_id,
        channel=conv.channel,
        status=conv.status,
        created_at=conv.created_at,
        resolved_at=conv.resolved_at,
        resolution_score=conv.resolution_score,
        messages=[
            MessageOut(
                id=_to_str_id(m.id),
                role=m.role,
                content=m.content,
                sources=m.sources,
                confidence=m.confidence,
                created_at=m.created_at,
            )
            for m in messages_sorted
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_jwt),
) -> None:
    """Soft-delete: mark conversation as resolved and clear messages content."""
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid UUID")

    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_uuid)
    )
    conv = result.scalar_one_or_none()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await db.execute(
        update(Conversation)
        .where(Conversation.id == conv_uuid)
        .values(status="resolved", resolved_at=datetime.now(timezone.utc))
    )
    await db.commit()
