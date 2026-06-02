"""
Voice persona config stored in Redis with env-var fallback.
Admin can update at runtime; changes take effect on the next API call (FR-11).
"""

import json
import logging
from dataclasses import asdict, dataclass

from app.config import settings
from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)
_REDIS_KEY = "convoai:config:voice"


@dataclass
class VoiceConfig:
    voice_id: str
    speed: float
    model: str


async def get_voice_config() -> VoiceConfig:
    redis = await get_redis()
    raw = await redis.get(_REDIS_KEY)
    if raw:
        try:
            data = json.loads(raw)
            return VoiceConfig(**data)
        except Exception:
            logger.warning("Corrupt voice config in Redis; using defaults")
    return VoiceConfig(
        voice_id=settings.elevenlabs_voice_id,
        speed=settings.elevenlabs_speed,
        model=settings.elevenlabs_model,
    )


async def set_voice_config(config: VoiceConfig) -> None:
    redis = await get_redis()
    await redis.set(_REDIS_KEY, json.dumps(asdict(config)))
    logger.info("Voice config updated: %s", config)
