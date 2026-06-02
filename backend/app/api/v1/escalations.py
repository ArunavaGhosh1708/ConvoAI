"""
Escalation ticket management (OQ-07).

  GET   /api/v1/admin/escalations        — list tickets, filter by status
  GET   /api/v1/admin/escalations/{id}   — single ticket detail
  PATCH /api/v1/admin/escalations/{id}   — update ticket status
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin_jwt
from app.models.escalation import EscalationTicket
from app.schemas.escalation import EscalationTicketOut, EscalationTicketPatch

router = APIRouter(tags=["admin"])


def _to_out(ticket: EscalationTicket) -> EscalationTicketOut:
    return EscalationTicketOut(
        id=str(ticket.id),
        conversation_id=str(ticket.conversation_id),
        session_id=ticket.session_id,
        reason=ticket.reason,
        status=ticket.status,
        context_chunks=ticket.context_chunks,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
    )


@router.get("/admin/escalations", response_model=list[EscalationTicketOut])
async def list_escalations(
    ticket_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> list[EscalationTicketOut]:
    stmt = select(EscalationTicket).order_by(EscalationTicket.created_at.desc()).limit(limit)
    if ticket_status:
        stmt = stmt.where(EscalationTicket.status == ticket_status)
    result = await db.execute(stmt)
    return [_to_out(t) for t in result.scalars()]


@router.get("/admin/escalations/{ticket_id}", response_model=EscalationTicketOut)
async def get_escalation(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> EscalationTicketOut:
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    result = await db.execute(
        select(EscalationTicket).where(EscalationTicket.id == ticket_uuid)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Escalation ticket not found")
    return _to_out(ticket)


@router.patch("/admin/escalations/{ticket_id}", response_model=EscalationTicketOut)
async def update_escalation_status(
    ticket_id: str,
    body: EscalationTicketPatch,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_admin_jwt),
) -> EscalationTicketOut:
    try:
        ticket_uuid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid UUID")

    result = await db.execute(
        select(EscalationTicket).where(EscalationTicket.id == ticket_uuid)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Escalation ticket not found")

    updates: dict = {"status": body.status}
    if body.status == "resolved" and ticket.resolved_at is None:
        updates["resolved_at"] = datetime.now(timezone.utc)

    await db.execute(
        update(EscalationTicket)
        .where(EscalationTicket.id == ticket_uuid)
        .values(**updates)
    )
    await db.commit()
    await db.refresh(ticket)
    return _to_out(ticket)
