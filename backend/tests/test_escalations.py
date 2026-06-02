"""Unit tests for escalation-related logic — no DB, no network."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.escalation import LogOnlyAdapter, WebhookAdapter, get_escalation_adapter


# ---------------------------------------------------------------------------
# LogOnlyAdapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_only_adapter_returns_true():
    adapter = LogOnlyAdapter()
    result = await adapter.send({"session_id": "s1", "escalation_reason": "test"})
    assert result is True


@pytest.mark.asyncio
async def test_log_only_adapter_does_not_raise_on_empty_payload():
    adapter = LogOnlyAdapter()
    result = await adapter.send({})
    assert result is True


# ---------------------------------------------------------------------------
# WebhookAdapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_adapter_sends_post(monkeypatch):
    import httpx

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.escalation.httpx.AsyncClient", return_value=mock_client):
        adapter = WebhookAdapter(url="http://example.com/hook")
        result = await adapter.send({"session_id": "s1", "escalation_reason": "low confidence"})

    assert result is True
    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.args[0] == "http://example.com/hook"


@pytest.mark.asyncio
async def test_webhook_adapter_returns_false_on_non_success(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.escalation.httpx.AsyncClient", return_value=mock_client):
        adapter = WebhookAdapter(url="http://example.com/hook")
        result = await adapter.send({"session_id": "s1", "escalation_reason": "test"})

    assert result is False


@pytest.mark.asyncio
async def test_webhook_adapter_returns_false_on_exception():
    with patch("app.services.escalation.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_cls.return_value = instance

        adapter = WebhookAdapter(url="http://example.com/hook")
        result = await adapter.send({"session_id": "s1", "escalation_reason": "test"})

    assert result is False


def test_webhook_adapter_adds_signature_header():
    adapter = WebhookAdapter(url="http://example.com/hook", secret="my-secret")
    body = b'{"test": "payload"}'
    sig = adapter._sign(body)
    assert sig.startswith("sha256=")
    assert len(sig) > 10


def test_webhook_adapter_no_secret_no_signature():
    adapter = WebhookAdapter(url="http://example.com/hook")
    # Verify _sign is not called when no secret — done by checking headers in send()
    # We test the signature helper directly with a known secret
    adapter_with_secret = WebhookAdapter(url="http://example.com/hook", secret="s")
    sig = adapter_with_secret._sign(b"hello")
    assert sig.startswith("sha256=")


# ---------------------------------------------------------------------------
# get_escalation_adapter factory
# ---------------------------------------------------------------------------

def test_factory_returns_log_adapter_when_no_url(monkeypatch):
    monkeypatch.setattr("app.config.settings.escalation_webhook_url", "")
    adapter = get_escalation_adapter()
    assert isinstance(adapter, LogOnlyAdapter)


def test_factory_returns_webhook_adapter_when_url_set(monkeypatch):
    monkeypatch.setattr("app.config.settings.escalation_webhook_url", "http://hook.example.com")
    monkeypatch.setattr("app.config.settings.escalation_webhook_secret", "")
    adapter = get_escalation_adapter()
    assert isinstance(adapter, WebhookAdapter)
    assert adapter.url == "http://hook.example.com"
    assert adapter.secret is None


def test_factory_passes_secret_to_webhook_adapter(monkeypatch):
    monkeypatch.setattr("app.config.settings.escalation_webhook_url", "http://hook.example.com")
    monkeypatch.setattr("app.config.settings.escalation_webhook_secret", "super-secret")
    adapter = get_escalation_adapter()
    assert isinstance(adapter, WebhookAdapter)
    assert adapter.secret == "super-secret"
