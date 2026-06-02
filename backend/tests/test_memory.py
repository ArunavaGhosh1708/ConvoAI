"""Unit tests for ConversationMemoryManager history helpers."""

import pytest

from app.agent.memory import ConversationMemoryManager
from langchain_core.messages import AIMessage, HumanMessage


def _make_mem() -> ConversationMemoryManager:
    return ConversationMemoryManager(redis=None, db=None)  # type: ignore


def test_history_to_lc_messages_basic():
    mem = _make_mem()
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    messages = mem.history_to_lc_messages(history)
    assert len(messages) == 2
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there!"


def test_history_to_lc_messages_skips_system():
    mem = _make_mem()
    history = [
        {"role": "system", "content": "Escalated"},
        {"role": "user", "content": "Can you help?"},
        {"role": "assistant", "content": "Sure!"},
    ]
    messages = mem.history_to_lc_messages(history)
    # system messages are skipped
    assert len(messages) == 2


def test_history_to_lc_messages_respects_window(monkeypatch):
    import app.agent.memory as mem_module
    monkeypatch.setattr("app.config.settings.memory_window", 2)

    mem = _make_mem()
    history = [
        {"role": "user", "content": f"msg {i}"}
        for i in range(10)
    ]
    messages = mem.history_to_lc_messages(history)
    # memory_window=2 → last 4 messages (2 turns × 2 roles)
    assert len(messages) <= 4


def test_history_to_lc_messages_empty():
    mem = _make_mem()
    assert mem.history_to_lc_messages([]) == []
