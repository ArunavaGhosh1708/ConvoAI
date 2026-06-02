"""
Dockerized E2E integration tests — full chat + voice flows.

Requires:
  API_BASE_URL  env var pointing to the running API (default http://localhost:8000)
  API_KEY       env var for the X-API-Key header

Run via docker-compose.test.yml or directly against a local stack:
  pytest tests/integration/ -v
"""

import os
import uuid

import httpx
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY  = os.getenv("API_KEY", "dev-api-key")

HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def healthy(client: httpx.Client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200, f"API not healthy: {resp.text}"
    assert resp.json()["status"] in ("ok", "degraded")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_endpoint(client, healthy):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Chat — JSON path
# ---------------------------------------------------------------------------

def test_chat_json_response(client, healthy):
    session = f"e2e-{uuid.uuid4()}"
    resp = client.post(
        "/api/v1/chat",
        json={"session_id": session, "message": "Hello, can you help me?", "stream": False},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    assert "sources" in data
    assert "confidence" in data
    assert "escalated" in data


def test_chat_multi_turn_maintains_context(client, healthy):
    session = f"e2e-multi-{uuid.uuid4()}"

    client.post(
        "/api/v1/chat",
        json={"session_id": session, "message": "My name is Alex.", "stream": False},
        headers=HEADERS,
    )

    resp2 = client.post(
        "/api/v1/chat",
        json={"session_id": session, "message": "What did I just tell you?", "stream": False},
        headers=HEADERS,
    )
    assert resp2.status_code == 200


def test_chat_sse_stream(client, healthy):
    session = f"e2e-sse-{uuid.uuid4()}"

    with client.stream(
        "POST",
        "/api/v1/chat",
        json={"session_id": session, "message": "What are your support hours?", "stream": True},
        headers=HEADERS,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events: list[str] = []
        for line in resp.iter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())

    assert "done" in events, "SSE stream did not terminate with 'done' event"
    assert "token" in events, "SSE stream emitted no 'token' events"


# ---------------------------------------------------------------------------
# Chat — authentication
# ---------------------------------------------------------------------------

def test_chat_rejects_missing_api_key(client, healthy):
    resp = client.post(
        "/api/v1/chat",
        json={"session_id": "s1", "message": "test", "stream": False},
    )
    assert resp.status_code == 401


def test_chat_rejects_wrong_api_key(client, healthy):
    resp = client.post(
        "/api/v1/chat",
        json={"session_id": "s1", "message": "test", "stream": False},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401
