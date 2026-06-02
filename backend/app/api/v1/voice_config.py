"""
Admin voice persona config endpoints (FR-11).
  GET /api/v1/admin/voice-config  — read current persona
  PUT /api/v1/admin/voice-config  — update persona (stored in Redis, live immediately)
"""

from fastapi import APIRouter, Depends

from app.middleware.auth import require_admin_jwt
from app.schemas.voice import VoiceConfigResponse, VoiceConfigUpdate
from app.services.voice_config import VoiceConfig, get_voice_config, set_voice_config

router = APIRouter(tags=["admin"])


@router.get("/admin/voice-config", response_model=VoiceConfigResponse)
async def get_voice_config_endpoint(
    _claims: dict = Depends(require_admin_jwt),
) -> VoiceConfigResponse:
    config = await get_voice_config()
    return VoiceConfigResponse(voice_id=config.voice_id, speed=config.speed, model=config.model)


@router.put("/admin/voice-config", response_model=VoiceConfigResponse)
async def update_voice_config_endpoint(
    body: VoiceConfigUpdate,
    _claims: dict = Depends(require_admin_jwt),
) -> VoiceConfigResponse:
    current = await get_voice_config()
    updated = VoiceConfig(
        voice_id=body.voice_id or current.voice_id,
        speed=body.speed    if body.speed is not None else current.speed,
        model=body.model    or current.model,
    )
    await set_voice_config(updated)
    return VoiceConfigResponse(voice_id=updated.voice_id, speed=updated.speed, model=updated.model)
