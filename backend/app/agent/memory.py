"""Hybrid Redis + PostgreSQL conversation memory manager."""

import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation, Message
from app.models.escalation import EscalationTicket
from app.rag.retrieval import RetrievedChunk
from app.services.escalation import get_escalation_adapter

logger = logging.getLogger(__name__)

_HISTORY_TTL = 86_400  # 24 hours
_KEY_PREFIX = "convoai:session"


def _history_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:history"


def _conv_id_key(session_id: str) -> str:
    return f"{_KEY_PREFIX}:{session_id}:conv_id"


class ConversationMemoryManager:
    def __init__(self, redis: Redis, db: AsyncSession) -> None:
        self.redis = redis
        self.db = db

    # ------------------------------------------------------------------
    # Conversation record
    # ------------------------------------------------------------------

    async def get_or_create_conversation(
        self, session_id: str, channel: str = "chat"
    ) -> Conversation:
        """Return the DB Conversation for this session, creating one if needed."""
        cached_id = await self.redis.get(_conv_id_key(session_id))

        if cached_id:
            result = await self.db.execute(
                select(Conversation).where(Conversation.id == uuid.UUID(cached_id))
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        # New session — create DB record (use session_id as user_id for now)
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=session_id,
            channel=channel,
            status="active",
        )
        self.db.add(conv)
        await self.db.flush()

        await self.redis.set(
            _conv_id_key(session_id), str(conv.id), ex=_HISTORY_TTL
        )
        logger.info("Created conversation %s for session %s", conv.id, session_id)
        return conv

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def load_history(self, session_id: str) -> list[dict]:
        """
        Return message history as a list of dicts: {"role": ..., "content": ...}.
        Tries Redis first; falls back to the last N turns from PostgreSQL.
        """
        raw = await self.redis.get(_history_key(session_id))
        if raw:
            return json.loads(raw)

        # Redis miss — rebuild from DB
        cached_id = await self.redis.get(_conv_id_key(session_id))
        if not cached_id:
            return []

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == uuid.UUID(cached_id))
            .where(Message.role.in_(["user", "assistant"]))
            .order_by(Message.created_at)
            .limit(settings.memory_window * 2)
        )
        messages = result.scalars().all()
        history = [{"role": m.role, "content": m.content} for m in messages]

        if history:
            await self.redis.set(
                _history_key(session_id), json.dumps(history), ex=_HISTORY_TTL
            )
        return history

    def history_to_lc_messages(self, history: list[dict]) -> list[BaseMessage]:
        """Convert stored history dicts to LangChain message objects."""
        out: list[BaseMessage] = []
        for msg in history[-(settings.memory_window * 2):]:
            if msg["role"] == "user":
                out.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                out.append(AIMessage(content=msg["content"]))
        return out

    # ------------------------------------------------------------------
    # Saving turns
    # ------------------------------------------------------------------

    async def save_turn(
        self,
        conversation: Conversation,
        session_id: str,
        user_content: str,
        assistant_content: str,
        chunks: list[RetrievedChunk],
        confidence: float,
    ) -> None:
        """Persist a completed turn to both Redis and PostgreSQL."""
        sources = [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "content": c.content[:200],
                "similarity": c.similarity,
                "metadata": c.metadata,
            }
            for c in chunks
        ]

        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=user_content,
        )
        assistant_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            sources=sources,
            confidence=confidence if confidence > 0 else None,
        )
        self.db.add_all([user_msg, assistant_msg])

        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation.id)
            .values(resolution_score=confidence)
        )

        # Update Redis history
        raw = await self.redis.get(_history_key(session_id))
        history: list[dict] = json.loads(raw) if raw else []
        history.append({"role": "user", "content": user_content})
        history.append({"role": "assistant", "content": assistant_content})
        await self.redis.set(
            _history_key(session_id), json.dumps(history), ex=_HISTORY_TTL
        )

    async def mark_escalated(
        self,
        conversation: Conversation,
        session_id: str,
        reason: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> dict:
        """Mark the conversation as escalated and build the escalation payload."""
        history = await self.load_history(session_id)

        payload = {
            "conversation_id": str(conversation.id),
            "session_id": session_id,
            "channel": conversation.channel,
            "escalation_reason": reason,
            "prior_turns": history,
            "retrieved_sources": [
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "similarity": c.similarity,
                    "content_preview": c.content[:200],
                }
                for c in retrieved_chunks
            ],
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation.id)
            .values(
                status="escalated",
                resolved_at=datetime.now(timezone.utc),
            )
        )

        system_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="system",
            content=f"Escalated to human agent. Reason: {reason}",
        )
        self.db.add(system_msg)

        # Persist escalation ticket for the admin queue
        ticket = EscalationTicket(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            session_id=session_id,
            reason=reason,
            status="open",
            context_chunks={
                "retrieved_sources": payload["retrieved_sources"],
                "prior_turns": history[-6:],  # last 3 user/assistant pairs
            },
        )
        self.db.add(ticket)

        # Fire-and-forget webhook (log-only when not configured)
        adapter = get_escalation_adapter()
        try:
            await adapter.send(payload)
        except Exception:
            logger.exception("Escalation adapter error for session %s", session_id)

        logger.info("Conversation %s escalated: %s", conversation.id, reason)
        return payload
