"""POST /api/v1/chat — SSE streaming (stream=true) or JSON (stream=false)."""

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Security
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import AgentContext
from app.agent.executor import run_agent, stream_agent_tokens
from app.agent.memory import ConversationMemoryManager
from app.config import settings
from app.database import get_db
from app.middleware.auth import require_api_key
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    EscalationPayload,
    SourceChunk,
    SourcesEvent,
    TokenEvent,
)
from app.services.redis_client import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

_FALLBACK = (
    "I'm sorry, I'm having trouble processing your request right now. "
    "Let me connect you with a human agent who can help."
)

_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",   # disable nginx buffering
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# Shared request logic
# ---------------------------------------------------------------------------

async def _run_and_persist(
    db: AsyncSession,
    redis: Redis,
    body: ChatRequest,
    context: AgentContext,
    response_text: str,
) -> tuple[str, EscalationPayload | None]:
    """
    Auto-escalate if needed, persist the turn, commit, and return
    (conversation_id, escalation_payload).
    """
    mem = ConversationMemoryManager(redis=redis, db=db)
    conversation = await mem.get_or_create_conversation(body.session_id, body.channel)

    if (
        not context.escalated
        and 0 < context.last_confidence < settings.escalation_confidence_threshold
    ):
        context.escalated = True
        context.escalation_reason = (
            f"Low retrieval confidence "
            f"({context.last_confidence:.3f} < {settings.escalation_confidence_threshold})"
        )
        logger.info(
            "Auto-escalating session %s confidence=%.3f",
            body.session_id,
            context.last_confidence,
        )

    await mem.save_turn(
        conversation=conversation,
        session_id=body.session_id,
        user_content=body.message,
        assistant_content=response_text,
        chunks=context.retrieved_chunks,
        confidence=context.last_confidence,
    )

    escalation_payload: EscalationPayload | None = None
    if context.escalated:
        raw = await mem.mark_escalated(
            conversation=conversation,
            session_id=body.session_id,
            reason=context.escalation_reason,
            retrieved_chunks=context.retrieved_chunks,
        )
        escalation_payload = EscalationPayload(**raw)

    await db.commit()
    return str(conversation.id), escalation_payload


def _build_sources(context: AgentContext) -> list[SourceChunk]:
    return [
        SourceChunk(
            chunk_id=c.id,
            document_id=c.document_id,
            content_preview=c.content[:200],
            similarity=c.similarity,
        )
        for c in context.retrieved_chunks
    ]


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------

async def _sse_generator(
    db: AsyncSession,
    redis: Redis,
    body: ChatRequest,
) -> AsyncGenerator[str, None]:
    mem = ConversationMemoryManager(redis=redis, db=db)
    context = AgentContext(session_id=body.session_id)

    # Pre-load history before streaming begins
    await mem.get_or_create_conversation(body.session_id, body.channel)
    history_dicts = await mem.load_history(body.session_id)
    chat_history = mem.history_to_lc_messages(history_dicts)

    full_response = ""

    try:
        async for token in stream_agent_tokens(
            db=db,
            context=context,
            user_input=body.message,
            chat_history=chat_history,
        ):
            full_response += token
            event = TokenEvent(token=token)
            yield f"event: token\ndata: {event.model_dump_json()}\n\n"

    except Exception as exc:
        logger.exception("Streaming agent failed for session %s: %s", body.session_id, exc)
        context.escalated = True
        context.escalation_reason = f"LLM unavailable: {type(exc).__name__}"
        full_response = _FALLBACK
        event = TokenEvent(token=_FALLBACK)
        yield f"event: token\ndata: {event.model_dump_json()}\n\n"

    # Persist after stream completes
    conversation_id, escalation_payload = await _run_and_persist(
        db, redis, body, context, full_response
    )

    # Emit sources event
    sources = _build_sources(context)
    sources_event = SourcesEvent(chunks=sources)
    yield f"event: sources\ndata: {sources_event.model_dump_json()}\n\n"

    # Emit done event
    done_event = DoneEvent(
        session_id=body.session_id,
        conversation_id=conversation_id,
        confidence=context.last_confidence,
        escalated=context.escalated,
        escalation_payload=escalation_payload,
    )
    yield f"event: done\ndata: {done_event.model_dump_json()}\n\n"


# ---------------------------------------------------------------------------
# Non-streaming (JSON) path
# ---------------------------------------------------------------------------

async def _json_chat(
    db: AsyncSession,
    redis: Redis,
    body: ChatRequest,
) -> ChatResponse:
    mem = ConversationMemoryManager(redis=redis, db=db)
    context = AgentContext(session_id=body.session_id)

    await mem.get_or_create_conversation(body.session_id, body.channel)
    history_dicts = await mem.load_history(body.session_id)
    chat_history = mem.history_to_lc_messages(history_dicts)

    try:
        response_text = await run_agent(
            db=db, context=context, user_input=body.message, chat_history=chat_history
        )
    except Exception as exc:
        logger.exception("Agent failed for session %s: %s", body.session_id, exc)
        context.escalated = True
        context.escalation_reason = f"LLM unavailable: {type(exc).__name__}"
        response_text = _FALLBACK

    conversation_id, escalation_payload = await _run_and_persist(
        db, redis, body, context, response_text
    )

    return ChatResponse(
        session_id=body.session_id,
        conversation_id=conversation_id,
        response=response_text,
        sources=_build_sources(context),
        confidence=context.last_confidence,
        escalated=context.escalated,
        escalation_payload=escalation_payload,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _auth: None = Security(require_api_key),
):
    if body.stream:
        return StreamingResponse(
            _sse_generator(db=db, redis=redis, body=body),
            headers=_SSE_HEADERS,
        )
    return await _json_chat(db=db, redis=redis, body=body)
