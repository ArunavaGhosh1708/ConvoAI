"""Unit tests for POST /api/v1/chat — JSON path, mocked agent + memory."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


_PAYLOAD = {"session_id": "test-session", "message": "Hello", "stream": False}
_API_KEY = "test-api-key"
_HEADERS = {"X-API-Key": _API_KEY}


def _mock_conv():
    import uuid
    from datetime import datetime, timezone
    conv = MagicMock()
    conv.id = uuid.uuid4()
    conv.channel = "chat"
    conv.status = "active"
    conv.created_at = datetime.now(timezone.utc)
    return conv


# ---------------------------------------------------------------------------
# JSON (non-streaming) path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_json_success(mock_client):
    client, mock_db, mock_redis = mock_client

    conv = _mock_conv()
    mock_redis.get.return_value = None  # no cached history
    mock_redis.set.return_value = None

    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as mock_mem_cls,
        patch("app.api.v1.chat.run_agent", new=AsyncMock(return_value="Great question!")) as _,
    ):
        mock_mem = AsyncMock()
        mock_mem.get_or_create_conversation.return_value = conv
        mock_mem.load_history.return_value = []
        mock_mem.history_to_lc_messages.return_value = []
        mock_mem.save_turn = AsyncMock()
        mock_mem.mark_escalated = AsyncMock()
        mock_mem_cls.return_value = mock_mem

        resp = await client.post("/api/v1/chat", json=_PAYLOAD, headers=_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Great question!"
    assert data["session_id"] == "test-session"
    assert "sources" in data
    assert "escalated" in data


@pytest.mark.asyncio
async def test_chat_json_escalates_on_low_confidence(mock_client):
    client, mock_db, mock_redis = mock_client

    conv = _mock_conv()

    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as mock_mem_cls,
        patch("app.api.v1.chat.run_agent", new=AsyncMock(return_value="I'm not sure")),
        patch("app.agent.context.AgentContext") as _,
    ):
        mock_mem = AsyncMock()
        mock_mem.get_or_create_conversation.return_value = conv
        mock_mem.load_history.return_value = []
        mock_mem.history_to_lc_messages.return_value = []
        mock_mem.save_turn = AsyncMock()
        mock_mem.mark_escalated = AsyncMock(return_value={
            "conversation_id": str(conv.id),
            "session_id": "test-session",
            "channel": "chat",
            "escalation_reason": "Low confidence",
            "prior_turns": [],
            "retrieved_sources": [],
            "escalated_at": "2026-06-01T00:00:00",
        })
        mock_mem_cls.return_value = mock_mem

        resp = await client.post("/api/v1/chat", json=_PAYLOAD, headers=_HEADERS)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_json_fallback_on_agent_error(mock_client):
    client, mock_db, mock_redis = mock_client
    conv = _mock_conv()

    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as mock_mem_cls,
        patch("app.api.v1.chat.run_agent", new=AsyncMock(side_effect=Exception("LLM error"))),
    ):
        mock_mem = AsyncMock()
        mock_mem.get_or_create_conversation.return_value = conv
        mock_mem.load_history.return_value = []
        mock_mem.history_to_lc_messages.return_value = []
        mock_mem.save_turn = AsyncMock()
        mock_mem.mark_escalated = AsyncMock(return_value={
            "conversation_id": str(conv.id),
            "session_id": "test-session",
            "channel": "chat",
            "escalation_reason": "LLM error",
            "prior_turns": [],
            "retrieved_sources": [],
            "escalated_at": "2026-06-01T00:00:00",
        })
        mock_mem_cls.return_value = mock_mem

        resp = await client.post("/api/v1/chat", json=_PAYLOAD, headers=_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert "trouble" in data["response"].lower()


@pytest.mark.asyncio
async def test_chat_requires_api_key(mock_client):
    client, _, _ = mock_client
    resp = await client.post("/api/v1/chat", json=_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_wrong_api_key_rejected(mock_client):
    client, _, _ = mock_client
    resp = await client.post(
        "/api/v1/chat", json=_PAYLOAD, headers={"X-API-Key": "wrong-key"}
    )
    assert resp.status_code == 401
