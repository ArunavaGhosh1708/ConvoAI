"""
Escalation adapter — forwards the escalation payload to a ticketing system.

OQ-07 decision gate: Zendesk / Salesforce / Freshdesk all accept generic webhooks.
Configure ESCALATION_WEBHOOK_URL to activate. ESCALATION_WEBHOOK_SECRET enables
HMAC-SHA256 request signing (compatible with Zendesk / Freshdesk webhook verification).

Default (no URL set): log-only adapter — payload is written to the app log.
"""

import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------

class EscalationAdapter(ABC):
    @abstractmethod
    async def send(self, payload: dict) -> bool:
        """Send escalation payload; return True on success."""


# ---------------------------------------------------------------------------
# Log-only (default when no webhook URL is configured)
# ---------------------------------------------------------------------------

class LogOnlyAdapter(EscalationAdapter):
    async def send(self, payload: dict) -> bool:
        logger.info(
            "ESCALATION (log-only) session=%s reason=%r",
            payload.get("session_id"),
            payload.get("escalation_reason"),
        )
        return True


# ---------------------------------------------------------------------------
# Webhook adapter (Zendesk / Salesforce / Freshdesk compatible)
# ---------------------------------------------------------------------------

class WebhookAdapter(EscalationAdapter):
    def __init__(self, url: str, secret: str | None = None) -> None:
        self.url    = url
        self.secret = secret

    def _sign(self, body: bytes) -> str:
        assert self.secret is not None
        sig = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    async def send(self, payload: dict) -> bool:
        body    = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-ConvoAI-Signature"] = self._sign(body)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.url, content=body, headers=headers)
                if resp.is_success:
                    logger.info(
                        "Escalation webhook delivered: session=%s status=%d",
                        payload.get("session_id"), resp.status_code,
                    )
                    return True
                else:
                    logger.error(
                        "Escalation webhook failed: session=%s status=%d body=%s",
                        payload.get("session_id"), resp.status_code, resp.text[:200],
                    )
                    return False
        except Exception as exc:
            logger.exception("Escalation webhook error for session %s: %s", payload.get("session_id"), exc)
            return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_escalation_adapter() -> EscalationAdapter:
    url    = settings.escalation_webhook_url
    secret = settings.escalation_webhook_secret
    if url:
        logger.debug("Using WebhookAdapter: %s", url)
        return WebhookAdapter(url=url, secret=secret or None)
    return LogOnlyAdapter()
