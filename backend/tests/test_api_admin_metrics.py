"""Unit tests for GET /api/v1/admin/metrics — mocked DB."""

import pytest
from tests.conftest import admin_jwt


@pytest.mark.asyncio
async def test_get_metrics_returns_all_fields(mock_client):
    client, mock_db, _ = mock_client
    # total, active, resolved, escalated, avg_conf
    mock_db.scalar.side_effect = [10, 3, 5, 2, 0.75]

    resp = await client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sessions"] == 10
    assert data["active_sessions"] == 3
    assert data["resolution_rate"] == pytest.approx(50.0)
    assert data["escalation_rate"] == pytest.approx(20.0)
    assert data["avg_confidence"] == pytest.approx(0.75)
    assert "refreshed_at" in data


@pytest.mark.asyncio
async def test_get_metrics_zero_total_avoids_div_by_zero(mock_client):
    client, mock_db, _ = mock_client
    mock_db.scalar.side_effect = [0, 0, 0, 0, None]

    resp = await client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {admin_jwt()}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["resolution_rate"] == 0.0
    assert data["escalation_rate"] == 0.0
    assert data["avg_confidence"] == 0.0


@pytest.mark.asyncio
async def test_get_metrics_requires_admin_jwt(mock_client):
    client, mock_db, _ = mock_client
    resp = await client.get("/api/v1/admin/metrics")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_metrics_rejects_user_jwt(mock_client):
    from tests.conftest import user_jwt
    client, mock_db, _ = mock_client
    resp = await client.get(
        "/api/v1/admin/metrics",
        headers={"Authorization": f"Bearer {user_jwt()}"},
    )
    assert resp.status_code == 403
