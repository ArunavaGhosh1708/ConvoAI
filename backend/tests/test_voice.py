"""Unit tests for the voice pipeline — no real API calls."""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Whisper service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_openai_returns_text(monkeypatch):
    monkeypatch.setattr("app.config.settings.whisper_backend", "openai")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value="Hello world")

    with patch("app.services.whisper.AsyncOpenAI", return_value=mock_client):
        from app.services.whisper import _transcribe_openai
        result = await _transcribe_openai(b"fake-audio", "audio/webm")

    assert result.text == "Hello world"
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_transcribe_sidecar_calls_http(monkeypatch):
    monkeypatch.setattr("app.config.settings.whisper_sidecar_url", "http://whisper:9000")

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hi there", "duration_ms": 120}
    mock_response.raise_for_status = MagicMock()

    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=mock_response)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__  = AsyncMock(return_value=False)

    with patch("app.services.whisper.httpx.AsyncClient", return_value=mock_cm):
        from app.services.whisper import _transcribe_sidecar
        result = await _transcribe_sidecar(b"fake-audio", "audio/webm")

    assert result.text == "Hi there"
    assert result.duration_ms == 120


def test_ext_from_content_type():
    from app.services.whisper import _ext_from_content_type
    assert _ext_from_content_type("audio/webm")        == "webm"
    assert _ext_from_content_type("audio/wav")         == "wav"
    assert _ext_from_content_type("audio/webm;codecs=opus") == "webm"
    assert _ext_from_content_type("audio/unknown")     == "webm"  # fallback


# ---------------------------------------------------------------------------
# Voice config service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_voice_config_redis_hit(monkeypatch):
    import json
    monkeypatch.setattr("app.config.settings.elevenlabs_voice_id", "default-id")
    monkeypatch.setattr("app.config.settings.elevenlabs_speed",    1.0)
    monkeypatch.setattr("app.config.settings.elevenlabs_model",    "eleven_turbo_v2_5")

    stored = {"voice_id": "custom-id", "speed": 1.5, "model": "eleven_turbo_v2"}
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps(stored))

    with patch("app.services.voice_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        from app.services.voice_config import get_voice_config
        config = await get_voice_config()

    assert config.voice_id == "custom-id"
    assert config.speed    == 1.5
    assert config.model    == "eleven_turbo_v2"


@pytest.mark.asyncio
async def test_get_voice_config_redis_miss_uses_defaults(monkeypatch):
    monkeypatch.setattr("app.config.settings.elevenlabs_voice_id", "default-voice")
    monkeypatch.setattr("app.config.settings.elevenlabs_speed",    1.0)
    monkeypatch.setattr("app.config.settings.elevenlabs_model",    "eleven_turbo_v2_5")

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.services.voice_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        from app.services.voice_config import get_voice_config
        config = await get_voice_config()

    assert config.voice_id == "default-voice"
    assert config.speed    == 1.0


@pytest.mark.asyncio
async def test_set_voice_config_writes_to_redis(monkeypatch):
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    with patch("app.services.voice_config.get_redis", new=AsyncMock(return_value=mock_redis)):
        from app.services.voice_config import VoiceConfig, set_voice_config
        await set_voice_config(VoiceConfig(voice_id="new-id", speed=0.9, model="eleven_monolingual_v1"))

    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    import json
    data = json.loads(call_args[0][1])
    assert data["voice_id"] == "new-id"
    assert data["speed"]    == 0.9


# ---------------------------------------------------------------------------
# Voice endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcribe_endpoint_returns_text(monkeypatch):
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")

    from fastapi.testclient import TestClient
    from app.main import app

    mock_result = MagicMock()
    mock_result.text       = "Transcribed text"
    mock_result.duration_ms = 180

    with patch("app.api.v1.voice.transcribe", new=AsyncMock(return_value=mock_result)):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/voice/transcribe",
            files={"audio": ("test.webm", b"fake-audio-data", "audio/webm")},
            headers={"X-API-Key": "test-api-key"},
        )

    assert resp.status_code == 200
    assert resp.json()["text"] == "Transcribed text"
    assert resp.json()["duration_ms"] == 180


@pytest.mark.asyncio
async def test_transcribe_endpoint_rejects_empty_audio(monkeypatch):
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("empty.webm", b"", "audio/webm")},
        headers={"X-API-Key": "test-api-key"},
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_transcribe_endpoint_requires_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.api_key", "real-key")

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("test.webm", b"data", "audio/webm")},
        # No X-API-Key header
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_synthesize_endpoint_rejects_empty_text(monkeypatch):
    monkeypatch.setattr("app.config.settings.api_key", "test-api-key")

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/api/v1/voice/synthesize",
        json={"text": "   "},
        headers={"X-API-Key": "test-api-key"},
    )

    assert resp.status_code == 400
