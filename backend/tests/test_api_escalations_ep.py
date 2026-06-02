"""Unit tests for admin escalation endpoints — mocked DB."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import admin_jwt


def _mock_ticket(status: str = "open") -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    t.conversation_id = uuid.uuid4()
    t.session_id = "sess-123"
    t.reason = "Low confidence"
    t.status = status
    t.context_chunks = None
    t.created_at = datetime.now(timezone.utc)
    t.resolved_at = None
    return t


# ---------------------------------------------------------------------------
# GET /admin/escalations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_escalations_returns_tickets(mock_client):
    client, mock_db, _ = mock_client
    tickets = [_mock_ticket("open"), _mock_ticket("in_progress")]

    result = MagicMock()
    result.scalars.return_value = tickets
    mock_db.execute.return_value = result

    resp = await client.get(
        "/api/v1/admin/escalations",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_escalations_filter_by_status(mock_client):
    client, mock_db, _ = mock_client
    result = MagicMock()
    result.scalars.return_value = [_mock_ticket("open")]
    mock_db.execute.return_value = result

    resp = await client.get(
        "/api/v1/admin/escalations?status=open",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_escalations_requires_admin(mock_client):
    client, _, _ = mock_client
    resp = await client.get("/api/v1/admin/escalations")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /admin/escalations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_escalation_found(mock_client):
    client, mock_db, _ = mock_client
    ticket = _mock_ticket()

    result = MagicMock()
    result.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = result

    resp = await client.get(
        f"/api/v1/admin/escalations/{ticket.id}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["reason"] == "Low confidence"


@pytest.mark.asyncio
async def test_get_escalation_not_found(mock_client):
    client, mock_db, _ = mock_client
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await client.get(
        f"/api/v1/admin/escalations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_escalation_invalid_uuid(mock_client):
    client, _, _ = mock_client
    resp = await client.get(
        "/api/v1/admin/escalations/not-a-uuid",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /admin/escalations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_escalation_advances_status(mock_client):
    client, mock_db, _ = mock_client
    ticket = _mock_ticket("open")
    ticket.status = "in_progress"  # reflects update

    result = MagicMock()
    result.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = result

    resp = await client.patch(
        f"/api/v1/admin/escalations/{ticket.id}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
        json={"status": "in_progress"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"


@pytest.mark.asyncio
async def test_patch_escalation_resolved_sets_resolved_at(mock_client):
    client, mock_db, _ = mock_client
    ticket = _mock_ticket("in_progress")
    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(timezone.utc)

    result = MagicMock()
    result.scalar_one_or_none.return_value = ticket
    mock_db.execute.return_value = result

    resp = await client.patch(
        f"/api/v1/admin/escalations/{ticket.id}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
        json={"status": "resolved"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patch_escalation_not_found(mock_client):
    client, mock_db, _ = mock_client
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await client.patch(
        f"/api/v1/admin/escalations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
        json={"status": "resolved"},
    )

    assert resp.status_code == 404
