"""Unit tests for agent executor — mocks all LangChain / OpenAI calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.context import AgentContext
from app.agent.executor import _build_prompt, create_agent_executor, run_agent, stream_agent_tokens


def _ctx() -> AgentContext:
    return AgentContext(session_id="exec-test-session")


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_returns_template():
    prompt = _build_prompt()
    # Verify messages are accessible (not an exception) and include system
    messages = prompt.messages
    assert any(hasattr(m, "prompt") or hasattr(m, "variable_name") for m in messages)


# ---------------------------------------------------------------------------
# create_agent_executor
# ---------------------------------------------------------------------------

def test_create_agent_executor_returns_executor():
    ctx = _ctx()

    with (
        patch("app.agent.executor.ChatOpenAI") as mock_llm_cls,
        patch("app.agent.executor.create_tool_calling_agent") as mock_create,
        patch("app.agent.executor.AgentExecutor") as mock_exec_cls,
    ):
        mock_llm_cls.return_value = MagicMock()
        mock_create.return_value = MagicMock()
        mock_exec_cls.return_value = MagicMock()

        executor = create_agent_executor(db=MagicMock(), context=ctx, streaming=False)

    mock_llm_cls.assert_called_once()
    mock_exec_cls.assert_called_once()
    assert executor is mock_exec_cls.return_value


def test_create_agent_executor_streaming_flag():
    ctx = _ctx()

    with (
        patch("app.agent.executor.ChatOpenAI") as mock_llm_cls,
        patch("app.agent.executor.create_tool_calling_agent"),
        patch("app.agent.executor.AgentExecutor"),
    ):
        mock_llm_cls.return_value = MagicMock()
        create_agent_executor(db=MagicMock(), context=ctx, streaming=True)

    call_kwargs = mock_llm_cls.call_args.kwargs
    assert call_kwargs.get("streaming") is True


# ---------------------------------------------------------------------------
# run_agent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_agent_returns_output():
    ctx = _ctx()
    mock_executor = AsyncMock()
    mock_executor.ainvoke.return_value = {"output": "Here is your answer."}

    with patch("app.agent.executor.create_agent_executor", return_value=mock_executor):
        result = await run_agent(
            db=MagicMock(),
            context=ctx,
            user_input="Hello",
            chat_history=[],
        )

    assert result == "Here is your answer."
    mock_executor.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_agent_passes_input_and_history():
    ctx = _ctx()
    from langchain_core.messages import HumanMessage

    mock_executor = AsyncMock()
    mock_executor.ainvoke.return_value = {"output": "reply"}
    history = [HumanMessage(content="prior message")]

    with patch("app.agent.executor.create_agent_executor", return_value=mock_executor):
        await run_agent(
            db=MagicMock(),
            context=ctx,
            user_input="current question",
            chat_history=history,
        )

    call_args = mock_executor.ainvoke.call_args.args[0]
    assert call_args["input"] == "current question"
    assert call_args["chat_history"] is history


# ---------------------------------------------------------------------------
# stream_agent_tokens
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_agent_tokens_yields_content():
    ctx = _ctx()

    # Build synthetic astream_events output
    def _make_chunk(content: str, tool_call_chunks=None):
        chunk = MagicMock()
        chunk.content = content
        chunk.tool_call_chunks = tool_call_chunks or []
        event = {
            "event": "on_chat_model_stream",
            "data": {"chunk": chunk},
        }
        return event

    events = [
        {"event": "on_chain_start", "data": {}},    # skipped
        _make_chunk("Hello"),
        _make_chunk(" world"),
        _make_chunk(""),   # empty — skipped
        {"event": "on_chain_end", "data": {}},      # skipped
    ]

    async def _astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_executor = MagicMock()
    mock_executor.astream_events = _astream_events

    with patch("app.agent.executor.create_agent_executor", return_value=mock_executor):
        tokens = []
        async for tok in stream_agent_tokens(
            db=MagicMock(),
            context=ctx,
            user_input="hi",
            chat_history=[],
        ):
            tokens.append(tok)

    assert tokens == ["Hello", " world"]


@pytest.mark.asyncio
async def test_stream_agent_tokens_skips_tool_call_chunks():
    ctx = _ctx()

    tool_chunk = MagicMock()
    tool_chunk.content = "tool json"
    tool_chunk.tool_call_chunks = [{"index": 0, "id": "tc1"}]  # non-empty → skip

    events = [{"event": "on_chat_model_stream", "data": {"chunk": tool_chunk}}]

    async def _astream_events(*args, **kwargs):
        for e in events:
            yield e

    mock_executor = MagicMock()
    mock_executor.astream_events = _astream_events

    with patch("app.agent.executor.create_agent_executor", return_value=mock_executor):
        tokens = [t async for t in stream_agent_tokens(
            db=MagicMock(), context=ctx, user_input="hi", chat_history=[]
        )]

    assert tokens == []
