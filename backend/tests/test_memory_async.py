"""Unit tests for ConversationMemoryManager async methods — mocked Redis + DB."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.memory import ConversationMemoryManager
from app.models.conversation import Conversation
from app.rag.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis(*, get_returns=None, set_returns=None) -> AsyncMock:
    redis = AsyncMock()
    redis.get.return_value = get_returns
    redis.set.return_value = set_returns
    return redis


def _make_db() -> AsyncMock:
    from sqlalchemy.ext.asyncio import AsyncSession
    return AsyncMock(spec=AsyncSession)


def _make_conv(session_id: str = "s1") -> MagicMock:
    conv = MagicMock(spec=Conversation)
    conv.id = uuid.uuid4()
    conv.user_id = session_id
    conv.channel = "chat"
    conv.status = "active"
    conv.created_at = datetime.now(timezone.utc)
    conv.resolved_at = None
    return conv


def _chunk(sim: float = 0.85) -> RetrievedChunk:
    return RetrievedChunk(
        id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        content="Relevant info",
        metadata={"filename": "doc.pdf"},
        similarity=sim,
    )


# ---------------------------------------------------------------------------
# get_or_create_conversation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_create_uses_cached_conv_id():
    conv = _make_conv()
    redis = _make_redis(get_returns=str(conv.id))
    db = _make_db()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = conv
    db.execute.return_value = result_mock

    mem = ConversationMemoryManager(redis=redis, db=db)
    returned = await mem.get_or_create_conversation("s1", "chat")

    assert returned is conv
    redis.get.assert_awaited()
    db.add.assert_not_called()   # no new conversation created


@pytest.mark.asyncio
async def test_get_or_create_makes_new_when_no_cache():
    redis = _make_redis(get_returns=None)  # cache miss
    db = _make_db()
    db.flush = AsyncMock()

    mem = ConversationMemoryManager(redis=redis, db=db)
    conv = await mem.get_or_create_conversation("s2", "chat")

    db.add.assert_called_once()
    redis.set.assert_awaited()   # stores new conv id


@pytest.mark.asyncio
async def test_get_or_create_makes_new_when_db_miss():
    # Redis has an id but DB row is gone (e.g. after db wipe)
    stale_id = str(uuid.uuid4())
    redis = _make_redis(get_returns=stale_id)
    db = _make_db()
    db.flush = AsyncMock()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None  # not in DB
    db.execute.return_value = result_mock

    mem = ConversationMemoryManager(redis=redis, db=db)
    conv = await mem.get_or_create_conversation("s3", "chat")

    db.add.assert_called_once()


# ---------------------------------------------------------------------------
# load_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_history_redis_hit():
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    redis = _make_redis(get_returns=json.dumps(history))
    db = _make_db()

    mem = ConversationMemoryManager(redis=redis, db=db)
    result = await mem.load_history("s1")

    assert result == history
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_load_history_redis_miss_no_conv_id():
    redis = AsyncMock()
    redis.get.return_value = None   # both history and conv_id miss
    db = _make_db()

    mem = ConversationMemoryManager(redis=redis, db=db)
    result = await mem.load_history("s1")

    assert result == []


@pytest.mark.asyncio
async def test_load_history_redis_miss_falls_back_to_db():
    conv_id = str(uuid.uuid4())
    redis = AsyncMock()
    redis.get.side_effect = [None, conv_id]  # history miss, then conv_id hit

    msg1 = MagicMock()
    msg1.role = "user"
    msg1.content = "question"
    msg2 = MagicMock()
    msg2.role = "assistant"
    msg2.content = "answer"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [msg1, msg2]
    db = _make_db()
    db.execute.return_value = result_mock

    mem = ConversationMemoryManager(redis=redis, db=db)
    result = await mem.load_history("s1")

    assert len(result) == 2
    assert result[0]["role"] == "user"
    redis.set.assert_awaited()   # cached back to Redis


# ---------------------------------------------------------------------------
# save_turn
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_turn_persists_messages():
    conv = _make_conv()
    history_json = json.dumps([])
    redis = _make_redis(get_returns=history_json)
    db = _make_db()

    mem = ConversationMemoryManager(redis=redis, db=db)
    await mem.save_turn(
        conversation=conv,
        session_id="s1",
        user_content="user msg",
        assistant_content="assistant reply",
        chunks=[_chunk(0.9)],
        confidence=0.9,
    )

    assert db.add_all.call_count == 1
    added = db.add_all.call_args.args[0]
    roles = {m.role for m in added}
    assert "user" in roles
    assert "assistant" in roles


@pytest.mark.asyncio
async def test_save_turn_updates_redis_history():
    conv = _make_conv()
    redis = _make_redis(get_returns=None)  # history cache miss
    db = _make_db()

    mem = ConversationMemoryManager(redis=redis, db=db)
    await mem.save_turn(
        conversation=conv,
        session_id="s1",
        user_content="q",
        assistant_content="a",
        chunks=[],
        confidence=0.0,
    )

    redis.set.assert_awaited()


# ---------------------------------------------------------------------------
# mark_escalated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_escalated_creates_ticket_and_marks_conv():
    conv = _make_conv()
    history = [{"role": "user", "content": "help"}, {"role": "assistant", "content": "..."}]
    redis = _make_redis(get_returns=json.dumps(history))
    db = _make_db()

    with patch("app.agent.memory.get_escalation_adapter") as mock_factory:
        mock_adapter = AsyncMock()
        mock_adapter.send.return_value = True
        mock_factory.return_value = mock_adapter

        mem = ConversationMemoryManager(redis=redis, db=db)
        payload = await mem.mark_escalated(
            conversation=conv,
            session_id="s1",
            reason="Cannot resolve issue",
            retrieved_chunks=[_chunk(0.7)],
        )

    assert "conversation_id" in payload
    assert payload["escalation_reason"] == "Cannot resolve issue"
    mock_adapter.send.assert_awaited_once()
    # system message + ticket both added
    assert db.add.call_count >= 2


@pytest.mark.asyncio
async def test_mark_escalated_swallows_adapter_errors():
    conv = _make_conv()
    redis = _make_redis(get_returns=json.dumps([]))
    db = _make_db()

    with patch("app.agent.memory.get_escalation_adapter") as mock_factory:
        mock_adapter = AsyncMock()
        mock_adapter.send.side_effect = Exception("webhook down")
        mock_factory.return_value = mock_adapter

        mem = ConversationMemoryManager(redis=redis, db=db)
        # Should not raise
        payload = await mem.mark_escalated(
            conversation=conv,
            session_id="s1",
            reason="test",
            retrieved_chunks=[],
        )

    assert "escalated_at" in payload
