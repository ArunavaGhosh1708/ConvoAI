"""
Runtime-configurable agent settings stored in Redis (FR-23).
Defaults fall back to environment variables. Admin can update without redeployment.
"""

import json
import logging
from dataclasses import asdict, dataclass

from app.config import settings
from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)
_REDIS_KEY = "convoai:config:agent"


@dataclass
class AgentConfig:
    escalation_confidence_threshold: float
    llm_temperature: float
    retrieval_top_k: int
    memory_window: int


async def get_agent_config() -> AgentConfig:
    redis = await get_redis()
    raw = await redis.get(_REDIS_KEY)
    if raw:
        try:
            data = json.loads(raw)
            return AgentConfig(**data)
        except Exception:
            logger.warning("Corrupt agent config in Redis; using env defaults")
    return AgentConfig(
        escalation_confidence_threshold=settings.escalation_confidence_threshold,
        llm_temperature=settings.llm_temperature,
        retrieval_top_k=settings.retrieval_top_k,
        memory_window=settings.memory_window,
    )


async def set_agent_config(config: AgentConfig) -> None:
    redis = await get_redis()
    await redis.set(_REDIS_KEY, json.dumps(asdict(config)))
    logger.info("Agent config updated: %s", config)
