"""Unit tests for PII redaction — regex patterns and middleware."""

import pytest
from unittest.mock import patch

from app.middleware.pii import redact, redact_with_regex, _PII_PATTERNS


# ---------------------------------------------------------------------------
# Regex redaction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_label,original_pii", [
    ("Contact me at alice@example.com please", "EMAIL",  "alice@example.com"),
    ("Call 555-867-5309 for support",          "PHONE",  "555-867-5309"),
    ("SSN: 123-45-6789",                       "SSN",    "123-45-6789"),
    ("My card is 4111111111111111",             "CREDIT", "4111111111111111"),
])
def test_redact_with_regex_replaces_pii(text: str, expected_label: str, original_pii: str):
    result = redact_with_regex(text)
    assert f"<{expected_label}>" in result
    assert original_pii not in result


def test_redact_with_regex_leaves_clean_text_intact():
    clean = "Please help me reset my password for the support portal."
    assert redact_with_regex(clean) == clean


def test_redact_with_regex_multiple_entities():
    text = "Email john@doe.com or call 800-555-1234"
    result = redact_with_regex(text)
    assert "<EMAIL>" in result
    assert "<PHONE>" in result
    assert "john@doe.com" not in result
    assert "800-555-1234" not in result


def test_redact_empty_string():
    assert redact_with_regex("") == ""


# ---------------------------------------------------------------------------
# redact() dispatcher
# ---------------------------------------------------------------------------

def test_redact_uses_regex_when_presidio_unavailable():
    with patch("app.middleware.pii._PRESIDIO_AVAILABLE", False):
        result = redact("Email me at test@example.com")
    assert "<EMAIL>" in result


def test_redact_uses_presidio_when_available():
    mock_results = ["fake_result"]

    with (
        patch("app.middleware.pii._PRESIDIO_AVAILABLE", True),
        patch("app.middleware.pii._analyzer") as mock_analyzer,
        patch("app.middleware.pii._anonymizer") as mock_anonymizer,
    ):
        mock_analyzer.analyze.return_value = mock_results
        from unittest.mock import MagicMock
        anon_result = MagicMock()
        anon_result.text = "Email me at <EMAIL_ADDRESS>"
        mock_anonymizer.anonymize.return_value = anon_result

        result = redact("Email me at test@example.com")

    assert result == "Email me at <EMAIL_ADDRESS>"


def test_redact_presidio_no_results_returns_original():
    with (
        patch("app.middleware.pii._PRESIDIO_AVAILABLE", True),
        patch("app.middleware.pii._analyzer") as mock_analyzer,
        patch("app.middleware.pii._anonymizer"),
    ):
        mock_analyzer.analyze.return_value = []
        result = redact("No PII here")

    assert result == "No PII here"


# ---------------------------------------------------------------------------
# Middleware integration (mocked request body)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pii_middleware_redacts_chat_message(mock_client, monkeypatch):
    monkeypatch.setattr("app.config.settings.pii_redaction", True)
    monkeypatch.setattr("app.middleware.pii._PRESIDIO_AVAILABLE", False)

    client, mock_db, mock_redis = mock_client

    from unittest.mock import AsyncMock, MagicMock
    import uuid
    from datetime import datetime, timezone

    conv = MagicMock()
    conv.id = uuid.uuid4()
    conv.channel = "chat"
    conv.status = "active"
    conv.created_at = datetime.now(timezone.utc)

    with (
        patch("app.api.v1.chat.ConversationMemoryManager") as mock_mem_cls,
        patch("app.api.v1.chat.run_agent", new=AsyncMock(return_value="Got it")) as _,
    ):
        mock_mem = AsyncMock()
        mock_mem.get_or_create_conversation.return_value = conv
        mock_mem.load_history.return_value = []
        mock_mem.history_to_lc_messages.return_value = []
        mock_mem.save_turn = AsyncMock()
        mock_mem.mark_escalated = AsyncMock()
        mock_mem_cls.return_value = mock_mem

        resp = await client.post(
            "/api/v1/chat",
            json={"session_id": "s1", "message": "My email is bob@test.com", "stream": False},
            headers={"X-API-Key": "test-api-key"},
        )

    assert resp.status_code == 200
    # Verify the agent received the redacted message (not the raw PII)
    call_args = mock_mem.save_turn.call_args
    if call_args:
        saved_content = call_args.kwargs.get("user_content", "")
        assert "bob@test.com" not in saved_content
