"""Unit tests for services: redis_client, agent_config, tts, gen_token."""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# redis_client
# ===========================================================================

@pytest.mark.asyncio
async def test_get_redis_singleton():
    """get_redis() returns the same instance on repeat calls."""
    import app.services.redis_client as rc_module

    # Reset module-level singleton
    rc_module._redis = None

    mock_redis_instance = AsyncMock()

    with patch("app.services.redis_client.Redis") as mock_redis_cls:
        mock_redis_cls.from_url.return_value = mock_redis_instance

        r1 = await rc_module.get_redis()
        r2 = await rc_module.get_redis()

    assert r1 is r2
    assert mock_redis_cls.from_url.call_count == 1
    rc_module._redis = None  # restore


@pytest.mark.asyncio
async def test_close_redis_clears_singleton():
    import app.services.redis_client as rc_module

    mock_instance = AsyncMock()
    rc_module._redis = mock_instance

    await rc_module.close_redis()

    mock_instance.aclose.assert_awaited_once()
    assert rc_module._redis is None


@pytest.mark.asyncio
async def test_close_redis_noop_when_already_none():
    import app.services.redis_client as rc_module
    rc_module._redis = None
    # Should not raise
    await rc_module.close_redis()


# ===========================================================================
# agent_config service
# ===========================================================================

@pytest.mark.asyncio
async def test_get_agent_config_redis_hit():
    from app.services.agent_config import get_agent_config, AgentConfig

    stored = {"escalation_confidence_threshold": 0.7, "llm_temperature": 0.1, "retrieval_top_k": 3, "memory_window": 5}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps(stored)

    with patch("app.services.agent_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        cfg = await get_agent_config()

    assert cfg.escalation_confidence_threshold == 0.7
    assert cfg.retrieval_top_k == 3


@pytest.mark.asyncio
async def test_get_agent_config_redis_miss_returns_env_defaults():
    from app.services.agent_config import get_agent_config

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("app.services.agent_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        cfg = await get_agent_config()

    assert cfg.escalation_confidence_threshold == pytest.approx(0.65)


@pytest.mark.asyncio
async def test_get_agent_config_corrupt_redis_falls_back():
    from app.services.agent_config import get_agent_config

    mock_redis = AsyncMock()
    mock_redis.get.return_value = "{ bad json !!!"

    with patch("app.services.agent_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        cfg = await get_agent_config()  # should not raise

    assert cfg is not None


@pytest.mark.asyncio
async def test_set_agent_config_writes_to_redis():
    from app.services.agent_config import set_agent_config, AgentConfig

    cfg = AgentConfig(escalation_confidence_threshold=0.8, llm_temperature=0.2, retrieval_top_k=10, memory_window=8)
    mock_redis = AsyncMock()

    with patch("app.services.agent_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        await set_agent_config(cfg)

    mock_redis.set.assert_awaited_once()
    raw = mock_redis.set.call_args.args[1]
    data = json.loads(raw)
    assert data["escalation_confidence_threshold"] == 0.8


# ===========================================================================
# TTS service
# ===========================================================================

def test_get_tts_client_raises_without_api_key(monkeypatch):
    import app.services.tts as tts_module
    tts_module._client = None
    monkeypatch.setattr("app.config.settings.elevenlabs_api_key", "")

    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        tts_module._get_client()


def test_get_tts_client_returns_instance_with_key(monkeypatch):
    import app.services.tts as tts_module
    tts_module._client = None
    monkeypatch.setattr("app.config.settings.elevenlabs_api_key", "fake-key")

    mock_elevenlabs_cls = MagicMock()
    mock_instance = MagicMock()
    mock_elevenlabs_cls.return_value = mock_instance

    with patch.dict(sys.modules, {"elevenlabs": MagicMock(AsyncElevenLabs=mock_elevenlabs_cls)}):
        client = tts_module._get_client()

    assert client is mock_instance
    tts_module._client = None  # restore


@pytest.mark.asyncio
async def test_synthesize_stream_yields_chunks(monkeypatch):
    import app.services.tts as tts_module
    monkeypatch.setattr("app.config.settings.elevenlabs_api_key", "fake-key")

    async def _fake_stream(**kwargs):
        yield b"audio-chunk-1"
        yield b"audio-chunk-2"
        yield b""  # empty — should be filtered

    mock_tts_client = MagicMock()
    mock_tts_client.text_to_speech.stream = MagicMock(return_value=_fake_stream())
    tts_module._client = mock_tts_client

    mock_voice_cfg = MagicMock()
    mock_voice_cfg.voice_id = "voice-123"
    mock_voice_cfg.speed = 1.0
    mock_voice_cfg.model = "eleven_turbo_v2_5"

    with (
        patch("app.services.tts.get_voice_config", new=AsyncMock(return_value=mock_voice_cfg)),
        patch.dict(sys.modules, {"elevenlabs.types": MagicMock(VoiceSettings=MagicMock())}),
    ):
        chunks = []
        async for chunk in tts_module.synthesize_stream("Hello world"):
            chunks.append(chunk)

    tts_module._client = None
    assert chunks == [b"audio-chunk-1", b"audio-chunk-2"]


# ===========================================================================
# gen_token utility
# ===========================================================================

def test_gen_token_main_prints_jwt(capsys):
    import jwt
    import sys
    from app.utils import gen_token

    with patch.object(sys, "argv", ["gen_token", "--role", "admin", "--sub", "test-admin"]):
        gen_token.main()

    captured = capsys.readouterr()
    token = captured.out.strip()

    # Verify token decodes correctly
    payload = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert payload["role"] == "admin"
    assert payload["sub"] == "test-admin"


def test_gen_token_default_role_is_user(capsys):
    import jwt
    import sys
    from app.utils import gen_token

    with patch.object(sys, "argv", ["gen_token"]):
        gen_token.main()

    captured = capsys.readouterr()
    token = captured.out.strip()
    payload = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert payload["role"] == "user"


def test_gen_token_custom_expiry(capsys):
    import jwt
    import sys
    import time
    from app.utils import gen_token

    with patch.object(sys, "argv", ["gen_token", "--exp", "7200"]):
        gen_token.main()

    captured = capsys.readouterr()
    token = captured.out.strip()
    payload = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert payload["exp"] - payload["iat"] == pytest.approx(7200, abs=5)


# ===========================================================================
# Celery worker configuration
# ===========================================================================

def test_ingest_document_task_is_registered():
    from app.worker.tasks import ingest_document
    assert ingest_document.name == "app.worker.tasks.ingest_document"


def test_ingest_document_task_retries_on_failure():
    from app.worker.tasks import ingest_document
    assert ingest_document.max_retries == 3


def test_ingest_document_task_autoretry_configured():
    from app.worker.tasks import ingest_document
    assert Exception in ingest_document.autoretry_for


def test_celery_app_has_correct_broker():
    from app.config import settings
    from app.worker.celery_app import celery_app
    assert celery_app.conf.broker_url == settings.celery_broker_url


def test_celery_app_task_acks_late():
    from app.worker.celery_app import celery_app
    assert celery_app.conf.task_acks_late is True
