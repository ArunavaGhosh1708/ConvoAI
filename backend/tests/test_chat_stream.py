"""Tests for the SSE streaming chat endpoint and rate limiter."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.context import AgentContext
from app.agent.executor import stream_agent_tokens
from app.rag.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# stream_agent_tokens — unit test the token generator
# ---------------------------------------------------------------------------

async def _fake_astream_events(inputs, version):
    """Simulates astream_events yielding token events."""
    tokens = ["Hello", " there", ", how can I help?"]
    for t in tokens:
        # Simulate on_chat_model_stream with content token
        mock_chunk = MagicMock()
        mock_chunk.content = t
        mock_chunk.tool_call_chunks = []
        yield {"event": "on_chat_model_stream", "data": {"chunk": mock_chunk}}

    # Also yield a tool-call event (should be filtered out)
    tool_chunk = MagicMock()
    tool_chunk.content = ""
    tool_chunk.tool_call_chunks = [{"name": "knowledge_retrieval"}]
    yield {"event": "on_chat_model_stream", "data": {"chunk": tool_chunk}}

    # Non-stream event (should be ignored)
    yield {"event": "on_tool_end", "data": {}}


@pytest.mark.asyncio
async def test_stream_agent_tokens_yields_only_content_tokens():
    context = AgentContext(session_id="test-session")
    mock_db = MagicMock()

    with patch("app.agent.executor.create_agent_executor") as mock_factory:
        mock_executor = MagicMock()
        mock_executor.astream_events = _fake_astream_events
        mock_factory.return_value = mock_executor

        tokens = []
        async for token in stream_agent_tokens(
            db=mock_db,
            context=context,
            user_input="Hello",
            chat_history=[],
        ):
            tokens.append(token)

    assert tokens == ["Hello", " there", ", how can I help?"]


@pytest.mark.asyncio
async def test_stream_agent_tokens_skips_empty_content():
    context = AgentContext(session_id="s1")

    async def _events(inputs, version):
        # Empty content token — should be skipped
        chunk = MagicMock()
        chunk.content = ""
        chunk.tool_call_chunks = []
        yield {"event": "on_chat_model_stream", "data": {"chunk": chunk}}

        # Real token
        chunk2 = MagicMock()
        chunk2.content = "Hi"
        chunk2.tool_call_chunks = []
        yield {"event": "on_chat_model_stream", "data": {"chunk": chunk2}}

    with patch("app.agent.executor.create_agent_executor") as mock_factory:
        mock_exec = MagicMock()
        mock_exec.astream_events = _events
        mock_factory.return_value = mock_exec

        tokens = [t async for t in stream_agent_tokens(MagicMock(), context, "q", [])]

    assert tokens == ["Hi"]


# ---------------------------------------------------------------------------
# _sse_generator — test the SSE format of the output
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_generator_emits_correct_event_types():
    from app.api.v1.chat import _sse_generator
    from app.schemas.chat import ChatRequest

    body = ChatRequest(session_id="sess-1", message="hi", stream=True)
    mock_db = MagicMock()
    mock_redis = MagicMock()

    # Patch out all external dependencies
    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as MockMem,
        patch("app.api.v1.chat.stream_agent_tokens") as mock_stream,
        patch("app.api.v1.chat._run_and_persist", new=AsyncMock(return_value=("conv-id-1", None))),
    ):
        mock_mem = MagicMock()
        mock_mem.get_or_create_conversation = AsyncMock(return_value=MagicMock(id="conv-id-1", channel="chat"))
        mock_mem.load_history = AsyncMock(return_value=[])
        mock_mem.history_to_lc_messages = MagicMock(return_value=[])
        MockMem.return_value = mock_mem

        async def _fake_tokens(*args, **kwargs):
            for t in ["Hello", " world"]:
                yield t

        mock_stream.side_effect = _fake_tokens

        events = []
        async for line in _sse_generator(mock_db, mock_redis, body):
            events.append(line)

    event_types = [
        line.split("\n")[0].replace("event: ", "")
        for line in events
        if line.startswith("event:")
    ]
    assert "token" in event_types
    assert "sources" in event_types
    assert "done" in event_types


@pytest.mark.asyncio
async def test_sse_generator_token_payloads_are_valid_json():
    from app.api.v1.chat import _sse_generator
    from app.schemas.chat import ChatRequest

    body = ChatRequest(session_id="sess-2", message="test", stream=True)

    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as MockMem,
        patch("app.api.v1.chat.stream_agent_tokens") as mock_stream,
        patch("app.api.v1.chat._run_and_persist", new=AsyncMock(return_value=("c1", None))),
    ):
        mock_mem = MagicMock()
        mock_mem.get_or_create_conversation = AsyncMock(return_value=MagicMock(id="c1", channel="chat"))
        mock_mem.load_history = AsyncMock(return_value=[])
        mock_mem.history_to_lc_messages = MagicMock(return_value=[])
        MockMem.return_value = mock_mem

        async def _tokens(*a, **kw):
            yield "Hi"

        mock_stream.side_effect = _tokens

        token_data_lines = []
        async for line in _sse_generator(MagicMock(), MagicMock(), body):
            if "event: token" in line:
                data_part = [l for l in line.split("\n") if l.startswith("data:")]
                if data_part:
                    token_data_lines.append(data_part[0][6:])  # strip "data: "

    assert token_data_lines, "Expected at least one token event"
    for data in token_data_lines:
        parsed = json.loads(data)
        assert "token" in parsed


# ---------------------------------------------------------------------------
# Rate limiter — unit test the sliding window logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_allows_under_limit():
    from app.middleware.rate_limit import RateLimitMiddleware
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    mock_redis = AsyncMock()
    # Simulate pipeline: zremrangebyscore, zadd, zcard=1, expire
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    mock_pipe.execute = AsyncMock(return_value=[None, None, 1, None])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    with patch("app.services.redis_client.get_redis", new=AsyncMock(return_value=mock_redis)):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ping")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_limit():
    from app.middleware.rate_limit import RateLimitMiddleware
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    mock_redis = AsyncMock()
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=False)
    # Simulate count=150 (above default limit of 100)
    mock_pipe.execute = AsyncMock(return_value=[None, None, 150, None])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    with (
        patch("app.middleware.rate_limit.get_redis", new=AsyncMock(return_value=mock_redis)),
        patch("app.middleware.rate_limit.settings.rate_limit_rpm", 100),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ping")
    assert resp.status_code == 429
    assert "Rate limit" in resp.json()["detail"]


def test_health_endpoint_exempt_from_rate_limit():
    """Health path must be in the exempt set."""
    from app.middleware.rate_limit import _EXEMPT
    assert "/api/v1/health" in _EXEMPT
