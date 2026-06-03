"""Unit tests for GET /api/v1/admin/review-queue."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from tests.conftest import admin_jwt


def _make_row(conv_id, user_id, channel, avg_conf, msg_count):
    row = MagicMock()
    row.id = conv_id
    row.user_id = user_id
    row.channel = channel
    row.avg_confidence = avg_conf
    row.message_count = msg_count
    row.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return row


@pytest.mark.asyncio
async def test_review_queue_returns_low_confidence_sessions(mock_client):
    import uuid
    client, mock_db, _ = mock_client

    conv_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _make_row(conv_id, "user-1", "chat", 0.45, 6),
    ]
    mock_db.execute.return_value = mock_result

    resp = await client.get(
        "/api/v1/admin/review-queue",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["conversation_id"] == str(conv_id)
    assert data[0]["avg_confidence"] == pytest.approx(0.45)
    assert data[0]["message_count"] == 6
    assert data[0]["channel"] == "chat"


@pytest.mark.asyncio
async def test_review_queue_empty_when_no_low_confidence(mock_client):
    client, mock_db, _ = mock_client

    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    resp = await client.get(
        "/api/v1/admin/review-queue",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_review_queue_requires_admin_jwt(mock_client):
    client, _, _ = mock_client
    resp = await client.get("/api/v1/admin/review-queue")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_review_queue_rejects_user_jwt(mock_client):
    from tests.conftest import user_jwt
    client, mock_db, _ = mock_client

    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    resp = await client.get(
        "/api/v1/admin/review-queue",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )
    assert resp.status_code == 403
