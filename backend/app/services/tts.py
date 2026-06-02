"""
ElevenLabs TTS service — streaming audio generator.

Uses elevenlabs 2.x SDK:  client.text_to_speech.stream(voice_id, text=...)
Latency budget: TTS ≤ 100 ms to first audio byte (PRD §4.2.5).
"""

import logging
from collections.abc import AsyncGenerator

from app.config import settings
from app.services.voice_config import get_voice_config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        if not settings.elevenlabs_api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not configured. "
                "Set it in your .env file to enable TTS."
            )
        from elevenlabs import AsyncElevenLabs
        _client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
    return _client


async def synthesize_stream(
    text: str,
    voice_id: str | None = None,
    speed: float | None = None,
) -> AsyncGenerator[bytes, None]:
    """
    Async generator that yields MP3 audio chunks from ElevenLabs.
    Wrapping this in a StreamingResponse gives sub-100 ms first-byte latency.
    """
    config = await get_voice_config()
    effective_voice_id = voice_id or config.voice_id
    effective_speed    = speed    if speed is not None else config.speed

    client = _get_client()
    logger.debug("TTS: voice=%s speed=%.1f model=%s", effective_voice_id, effective_speed, config.model)

    from elevenlabs.types import VoiceSettings

    async for chunk in client.text_to_speech.stream(
        voice_id=effective_voice_id,
        text=text,
        model_id=config.model,
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.45,
            similarity_boost=0.75,
            speed=effective_speed,
        ),
    ):
        if isinstance(chunk, bytes) and chunk:
            yield chunk
