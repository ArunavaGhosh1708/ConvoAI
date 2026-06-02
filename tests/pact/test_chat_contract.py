"""
Pact consumer contract tests — React frontend ↔ FastAPI backend.

Verifies that the backend honours the contracts expected by the React
frontend for the /api/v1/chat and /api/v1/admin/metrics endpoints.

Requires: pip install pact-python
Run:
  pytest tests/pact/ -v

The generated pact files are written to tests/pact/pacts/ and can be
published to a Pact Broker for provider verification.
"""

import json
import os
import uuid

import pytest

try:
    from pact import Consumer, Provider
    _PACT_AVAILABLE = True
except ImportError:
    _PACT_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _PACT_AVAILABLE,
    reason="pact-python not installed — run: pip install pact-python",
)

PACT_DIR  = os.path.join(os.path.dirname(__file__), "pacts")
PACT_HOST = "localhost"
PACT_PORT = 1234


@pytest.fixture(scope="module")
def pact():
    consumer = Consumer("ConvoAI-React-Frontend")
    provider = Provider("ConvoAI-FastAPI-Backend")
    p = consumer.has_pact_with(
        provider,
        host_name=PACT_HOST,
        port=PACT_PORT,
        pact_dir=PACT_DIR,
        log_dir=PACT_DIR,
    )
    p.start_service()
    yield p
    p.stop_service()


# ---------------------------------------------------------------------------
# Contract: POST /api/v1/chat (JSON response)
# ---------------------------------------------------------------------------

def test_chat_json_contract(pact):
    session_id = str(uuid.uuid4())

    expected_response = {
        "session_id":         session_id,
        "conversation_id":    "some-uuid",
        "response":           "Here is the answer to your question.",
        "sources":            [],
        "confidence":         0.85,
        "escalated":          False,
        "escalation_payload": None,
    }

    (
        pact
        .given("knowledge base has documents indexed")
        .upon_receiving("a chat request with stream=false")
        .with_request(
            method="POST",
            path="/api/v1/chat",
            headers={"X-API-Key": "dev-api-key", "Content-Type": "application/json"},
            body={
                "session_id": session_id,
                "message":    "What is your return policy?",
                "stream":     False,
                "channel":    "chat",
            },
        )
        .will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_response,
        )
    )

    import httpx
    with pact:
        resp = httpx.post(
            f"http://{PACT_HOST}:{PACT_PORT}/api/v1/chat",
            json={
                "session_id": session_id,
                "message":    "What is your return policy?",
                "stream":     False,
                "channel":    "chat",
            },
            headers={"X-API-Key": "dev-api-key"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "response" in body
    assert "session_id" in body
    assert "escalated" in body


# ---------------------------------------------------------------------------
# Contract: GET /api/v1/admin/metrics
# ---------------------------------------------------------------------------

def test_metrics_contract(pact):
    expected_metrics = {
        "total_sessions":  10,
        "active_sessions": 3,
        "resolution_rate": 50.0,
        "escalation_rate": 20.0,
        "avg_confidence":  0.75,
        "refreshed_at":    "2026-06-01T12:00:00+00:00",
    }

    (
        pact
        .given("some conversations exist in the database")
        .upon_receiving("an admin metrics request")
        .with_request(
            method="GET",
            path="/api/v1/admin/metrics",
            headers={"Authorization": "Bearer valid-admin-jwt"},
        )
        .will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_metrics,
        )
    )

    import httpx
    with pact:
        resp = httpx.get(
            f"http://{PACT_HOST}:{PACT_PORT}/api/v1/admin/metrics",
            headers={"Authorization": "Bearer valid-admin-jwt"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "total_sessions" in body
    assert "resolution_rate" in body
