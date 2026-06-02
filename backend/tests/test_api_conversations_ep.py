"""Unit tests for GET/DELETE /api/v1/conversations/{id} — mocked DB."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import user_jwt, admin_jwt


def _mock_conv(status: str = "active") -> MagicMock:
    conv = MagicMock()
    conv.id = uuid.uuid4()
    conv.user_id = "test-user"
    conv.channel = "chat"
    conv.status = status
    conv.created_at = datetime.now(timezone.utc)
    conv.resolved_at = None
    conv.resolution_score = 0.85
    conv.messages = []
    return conv


# ---------------------------------------------------------------------------
# GET /conversations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_conversation_found(mock_client):
    client, mock_db, _ = mock_client
    conv = _mock_conv()

    result = MagicMock()
    result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = result

    resp = await client.get(
        f"/api/v1/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(conv.id)
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_get_conversation_not_found(mock_client):
    client, mock_db, _ = mock_client

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await client.get(
        f"/api/v1/conversations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_invalid_uuid(mock_client):
    client, _, _ = mock_client

    resp = await client.get(
        "/api/v1/conversations/not-a-uuid",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_conversation_requires_jwt(mock_client):
    client, _, _ = mock_client
    resp = await client.get(f"/api/v1/conversations/{uuid.uuid4()}")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /conversations/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_conversation_success(mock_client):
    client, mock_db, _ = mock_client
    conv = _mock_conv()

    result = MagicMock()
    result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = result

    resp = await client.delete(
        f"/api/v1/conversations/{conv.id}",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_conversation_not_found(mock_client):
    client, mock_db, _ = mock_client

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    resp = await client.delete(
        f"/api/v1/conversations/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_invalid_uuid(mock_client):
    client, _, _ = mock_client
    resp = await client.delete(
        "/api/v1/conversations/not-a-uuid",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )
    assert resp.status_code == 422
