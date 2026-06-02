"""LangChain tools: KnowledgeRetrievalTool and EscalationTool."""

import logging
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context import AgentContext
from app.config import settings
from app.rag.retrieval import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class KnowledgeRetrievalInput(BaseModel):
    query: str = Field(description="The search query to find relevant knowledge chunks")


class EscalationInput(BaseModel):
    reason: str = Field(
        description="Brief explanation of why escalation to a human agent is needed"
    )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No relevant knowledge found for this query."

    lines = [f"Found {len(chunks)} relevant knowledge chunk(s):\n"]
    for i, chunk in enumerate(chunks, 1):
        filename = chunk.metadata.get("filename", "unknown")
        lines.append(
            f"[{i}] similarity={chunk.similarity:.3f} | source={filename}\n"
            f"{chunk.content.strip()}\n"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class KnowledgeRetrievalTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "knowledge_retrieval"
    description: str = (
        "Search the internal knowledge base for information relevant to the customer's question. "
        "Returns the most relevant document excerpts with similarity scores. "
        "Always call this tool before answering factual questions."
    )
    args_schema: Type[BaseModel] = KnowledgeRetrievalInput

    db: Any  # AsyncSession — not annotated to avoid Pydantic serialisation issues
    context: Any  # AgentContext

    def _run(self, query: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async agent runner")

    async def _arun(self, query: str) -> str:
        chunks = await retrieve(self.db, query)

        self.context.retrieved_chunks = chunks
        self.context.last_confidence = chunks[0].similarity if chunks else 0.0

        logger.debug(
            "KnowledgeRetrievalTool: query=%r top_confidence=%.3f chunks=%d",
            query[:60],
            self.context.last_confidence,
            len(chunks),
        )
        return _format_chunks(chunks)


class EscalationTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "escalate_to_human"
    description: str = (
        "Transfer this conversation to a human support agent. "
        "Use when the knowledge base cannot resolve the issue, confidence is low, "
        "or the customer requests a human. Provide a clear reason."
    )
    args_schema: Type[BaseModel] = EscalationInput

    context: Any  # AgentContext

    def _run(self, reason: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async agent runner")

    async def _arun(self, reason: str) -> str:
        self.context.escalated = True
        self.context.escalation_reason = reason
        logger.info(
            "EscalationTool called: session=%s reason=%r",
            self.context.session_id,
            reason,
        )
        return (
            "Escalation confirmed. The conversation will be transferred to a human agent "
            f"with full context. Reason: {reason}"
        )


def build_tools(db: AsyncSession, context: AgentContext) -> list[BaseTool]:
    return [
        KnowledgeRetrievalTool(db=db, context=context),
        EscalationTool(context=context),
    ]
