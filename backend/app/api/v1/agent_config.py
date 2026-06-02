"""
Admin agent configuration endpoint (FR-23).
  GET /api/v1/admin/agent-config  — read current settings
  PUT /api/v1/admin/agent-config  — update settings (live, no redeploy)
"""

from fastapi import APIRouter, Depends

from app.middleware.auth import require_admin_jwt
from app.schemas.document import AgentConfigSchema, AgentConfigUpdate
from app.services.agent_config import AgentConfig, get_agent_config, set_agent_config

router = APIRouter(tags=["admin"])


@router.get("/admin/agent-config", response_model=AgentConfigSchema)
async def get_config(_claims: dict = Depends(require_admin_jwt)) -> AgentConfigSchema:
    cfg = await get_agent_config()
    return AgentConfigSchema(
        escalation_confidence_threshold=cfg.escalation_confidence_threshold,
        llm_temperature=cfg.llm_temperature,
        retrieval_top_k=cfg.retrieval_top_k,
        memory_window=cfg.memory_window,
    )


@router.put("/admin/agent-config", response_model=AgentConfigSchema)
async def update_config(
    body: AgentConfigUpdate,
    _claims: dict = Depends(require_admin_jwt),
) -> AgentConfigSchema:
    current = await get_agent_config()
    updated = AgentConfig(
        escalation_confidence_threshold=(
            body.escalation_confidence_threshold
            if body.escalation_confidence_threshold is not None
            else current.escalation_confidence_threshold
        ),
        llm_temperature=(
            body.llm_temperature if body.llm_temperature is not None else current.llm_temperature
        ),
        retrieval_top_k=(
            body.retrieval_top_k if body.retrieval_top_k is not None else current.retrieval_top_k
        ),
        memory_window=(
            body.memory_window if body.memory_window is not None else current.memory_window
        ),
    )
    await set_agent_config(updated)
    return AgentConfigSchema(
        escalation_confidence_threshold=updated.escalation_confidence_threshold,
        llm_temperature=updated.llm_temperature,
        retrieval_top_k=updated.retrieval_top_k,
        memory_window=updated.memory_window,
    )
