"""
Whisper STT service.

OQ-03 decision gate:
  whisper_backend = "openai"  → OpenAI hosted Whisper API (default; no sidecar needed)
  whisper_backend = "sidecar" → self-hosted faster-whisper sidecar on :9000

Both paths return a TranscriptionResult with the plain text and wall-clock duration.
"""

import io
import logging
import time
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    duration_ms: int


async def transcribe(audio_data: bytes, content_type: str = "audio/webm") -> TranscriptionResult:
    """Route to the configured Whisper backend."""
    if settings.whisper_backend == "sidecar":
        return await _transcribe_sidecar(audio_data, content_type)
    return await _transcribe_openai(audio_data, content_type)


# ---------------------------------------------------------------------------
# OpenAI hosted Whisper (default)
# ---------------------------------------------------------------------------

async def _transcribe_openai(audio_data: bytes, content_type: str) -> TranscriptionResult:
    ext = _ext_from_content_type(content_type)
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    buf = io.BytesIO(audio_data)
    buf.name = f"audio.{ext}"

    t0 = time.monotonic()
    result = await client.audio.transcriptions.create(
        model="whisper-1",
        file=buf,
        response_format="text",
        language="en",
    )
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info("Whisper/OpenAI: %dms for %d bytes", duration_ms, len(audio_data))
    return TranscriptionResult(text=str(result).strip(), duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Self-hosted sidecar
# ---------------------------------------------------------------------------

async def _transcribe_sidecar(audio_data: bytes, content_type: str) -> TranscriptionResult:
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.whisper_sidecar_url}/transcribe",
            files={"audio": ("audio.webm", audio_data, content_type)},
        )
        response.raise_for_status()
        data = response.json()

    duration_ms = data.get("duration_ms", int((time.monotonic() - t0) * 1000))
    logger.info("Whisper/sidecar: %dms for %d bytes", duration_ms, len(audio_data))
    return TranscriptionResult(text=data["text"].strip(), duration_ms=duration_ms)


def _ext_from_content_type(content_type: str) -> str:
    return {
        "audio/webm": "webm",
        "audio/wav":  "wav",
        "audio/mp4":  "mp4",
        "audio/ogg":  "ogg",
        "audio/mpeg": "mp3",
    }.get(content_type.split(";")[0].strip(), "webm")
