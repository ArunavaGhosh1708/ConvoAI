"""Unit tests for GET /api/v1/health — mocked DB."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_health_ok_when_db_reachable(mock_client):
    client, mock_db, _ = mock_client
    mock_db.execute.return_value = MagicMock()

    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_when_db_fails(mock_client):
    client, mock_db, _ = mock_client
    mock_db.execute.side_effect = Exception("connection refused")

    resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "unreachable"
