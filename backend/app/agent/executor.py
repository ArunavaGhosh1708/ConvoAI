"""LangChain agent executor factory — sync invoke and streaming."""

import logging
from collections.abc import AsyncGenerator

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.circuit_breaker import CircuitBreakerOpen, llm_breaker
from app.agent.context import AgentContext
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import build_tools
from app.config import settings

logger = logging.getLogger(__name__)


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


def create_agent_executor(
    db: AsyncSession,
    context: AgentContext,
    streaming: bool = False,
) -> AgentExecutor:
    """
    Build a fresh AgentExecutor for one request.
    Pass streaming=True to enable token-level streaming via astream_events.
    """
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key,
        streaming=streaming,
    )
    tools = build_tools(db=db, context=context)
    prompt = _build_prompt()
    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=settings.agent_max_iterations,
        handle_parsing_errors=True,
        verbose=settings.app_env == "development",
    )


async def run_agent(
    db: AsyncSession,
    context: AgentContext,
    user_input: str,
    chat_history: list[BaseMessage],
) -> str:
    """Non-streaming invoke. Returns the full response text."""
    llm_breaker.before_call()
    executor = create_agent_executor(db=db, context=context, streaming=False)
    try:
        result = await executor.ainvoke(
            {"input": user_input, "chat_history": chat_history}
        )
        llm_breaker.on_success()
        return result["output"]
    except CircuitBreakerOpen:
        raise
    except Exception:
        llm_breaker.on_failure()
        raise


async def stream_agent_tokens(
    db: AsyncSession,
    context: AgentContext,
    user_input: str,
    chat_history: list[BaseMessage],
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields final-answer tokens as they are produced.

    Uses astream_events v2 and filters out tool-call JSON tokens so only
    the natural-language response reaches the caller.
    """
    llm_breaker.before_call()
    executor = create_agent_executor(db=db, context=context, streaming=True)

    try:
        async for event in executor.astream_events(
            {"input": user_input, "chat_history": chat_history},
            version="v2",
        ):
            if event["event"] != "on_chat_model_stream":
                continue

            chunk = event["data"]["chunk"]
            content = chunk.content if isinstance(chunk.content, str) else ""
            # Skip empty content and tool-call token chunks
            if content and not getattr(chunk, "tool_call_chunks", None):
                yield content

        llm_breaker.on_success()
    except CircuitBreakerOpen:
        raise
    except Exception:
        llm_breaker.on_failure()
        raise
