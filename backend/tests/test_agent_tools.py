"""Unit tests for agent tools and memory helpers — no DB, no OpenAI."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.context import AgentContext
from app.agent.tools import (
    EscalationTool,
    KnowledgeRetrievalTool,
    _format_chunks,
    build_tools,
)
from app.rag.retrieval import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(id_: str, sim: float, content: str = "chunk content") -> RetrievedChunk:
    return RetrievedChunk(
        id=id_,
        document_id="doc-1",
        content=content,
        metadata={"filename": "manual.pdf"},
        similarity=sim,
    )


def _make_context(session_id: str = "test-session") -> AgentContext:
    return AgentContext(session_id=session_id)


# ---------------------------------------------------------------------------
# _format_chunks
# ---------------------------------------------------------------------------

def test_format_chunks_empty():
    result = _format_chunks([])
    assert "No relevant knowledge" in result


def test_format_chunks_includes_filename():
    chunks = [_chunk("1", 0.92, "Some content about returns")]
    result = _format_chunks(chunks)
    assert "manual.pdf" in result
    assert "0.920" in result
    assert "Some content about returns" in result


def test_format_chunks_numbers_entries():
    chunks = [_chunk(str(i), 0.9 - i * 0.05) for i in range(3)]
    result = _format_chunks(chunks)
    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" in result


# ---------------------------------------------------------------------------
# KnowledgeRetrievalTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_knowledge_retrieval_updates_context():
    context = _make_context()
    mock_db = MagicMock()
    chunks = [_chunk("a", 0.91), _chunk("b", 0.82)]

    tool = KnowledgeRetrievalTool(db=mock_db, context=context)

    with patch("app.agent.tools.retrieve", new=AsyncMock(return_value=chunks)):
        result = await tool._arun("what is the return policy?")

    assert context.last_confidence == pytest.approx(0.91)
    assert context.retrieved_chunks == chunks
    assert "manual.pdf" in result


@pytest.mark.asyncio
async def test_knowledge_retrieval_no_results_sets_zero_confidence():
    context = _make_context()
    tool = KnowledgeRetrievalTool(db=MagicMock(), context=context)

    with patch("app.agent.tools.retrieve", new=AsyncMock(return_value=[])):
        result = await tool._arun("something obscure")

    assert context.last_confidence == 0.0
    assert context.retrieved_chunks == []
    assert "No relevant knowledge" in result


# ---------------------------------------------------------------------------
# EscalationTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_escalation_tool_sets_context_flags():
    context = _make_context()
    tool = EscalationTool(context=context)

    result = await tool._arun("Customer needs a refund beyond policy limits")

    assert context.escalated is True
    assert "refund" in context.escalation_reason.lower()
    assert "human agent" in result.lower()


@pytest.mark.asyncio
async def test_escalation_tool_preserves_reason():
    context = _make_context()
    tool = EscalationTool(context=context)
    reason = "Issue requires account verification which I cannot perform"

    await tool._arun(reason)

    assert context.escalation_reason == reason


# ---------------------------------------------------------------------------
# build_tools
# ---------------------------------------------------------------------------

def test_build_tools_returns_both_tools():
    context = _make_context()
    tools = build_tools(db=MagicMock(), context=context)
    names = {t.name for t in tools}
    assert "knowledge_retrieval" in names
    assert "escalate_to_human" in names


def test_build_tools_share_context():
    context = _make_context()
    tools = build_tools(db=MagicMock(), context=context)
    for tool in tools:
        assert tool.context is context
