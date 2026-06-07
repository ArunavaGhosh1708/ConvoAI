"""
PII redaction middleware — strips emails, phone numbers, SSNs, and card
numbers from user message content before it reaches the agent or is persisted.

Uses Presidio when available (production); falls back to compiled regex
patterns for CI environments without the spaCy model installed.

Activation: set PII_REDACTION=true in environment.

Implemented as a raw ASGI middleware (not BaseHTTPMiddleware) because
Starlette's BaseHTTPMiddleware cannot modify request bodies — it buffers
the original receive and ignores a swapped-in receive callable.
"""

import json
import logging
import re
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Presidio (optional heavy dependency)
# ---------------------------------------------------------------------------

_PRESIDIO_AVAILABLE = False
_analyzer = None
_anonymizer = None


def _try_load_presidio() -> bool:
    global _analyzer, _anonymizer, _PRESIDIO_AVAILABLE
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
        _analyzer = AnalyzerEngine()
        _anonymizer = AnonymizerEngine()
        _PRESIDIO_AVAILABLE = True
        logger.info("PII: Presidio loaded — full entity recognition active")
        return True
    except Exception as exc:
        logger.info("PII: Presidio not available (%s) — using regex fallback", exc)
        return False


# ---------------------------------------------------------------------------
# Regex fallback patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL",  re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b")),
    ("PHONE",  re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("SSN",    re.compile(r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0{4})\d{4}\b")),
    ("CREDIT", re.compile(r"\b(?:4\d{12}(?:\d{3})?|5[1-5]\d{14}|3[47]\d{13})\b")),
]


def redact_with_regex(text: str) -> str:
    for label, pattern in _PII_PATTERNS:
        text = pattern.sub(f"<{label}>", text)
    return text


def redact_with_presidio(text: str) -> str:
    assert _analyzer is not None and _anonymizer is not None
    results = _analyzer.analyze(text=text, language="en")
    if not results:
        return text
    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text


def redact(text: str) -> str:
    """Public entry point: prefer Presidio, fall back to regex."""
    if _PRESIDIO_AVAILABLE:
        return redact_with_presidio(text)
    return redact_with_regex(text)


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------

class PIIRedactionMiddleware:
    """
    Raw ASGI middleware that intercepts POST /api/v1/chat requests and
    redacts PII from the `message` field before any route handler sees it.
    Only active when settings.pii_redaction is True.
    """

    def __init__(self, app) -> None:
        self.app = app
        _try_load_presidio()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path   = scope.get("path", "")

        if method == "POST" and path.endswith("/chat") and settings.pii_redaction:
            receive = await self._redacting_receive(receive)

        await self.app(scope, receive, send)

    async def _redacting_receive(self, receive: Callable) -> Callable:
        """Read + redact the full body, return a replacement receive callable."""
        body = b""
        more_body = True
        while more_body:
            message   = await receive()
            body     += message.get("body", b"")
            more_body  = message.get("more_body", False)

        body = self._redact_body(body)

        async def redacted_receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        return redacted_receive

    def _redact_body(self, body: bytes) -> bytes:
        try:
            data = json.loads(body)
            if "message" in data:
                original = data["message"]
                data["message"] = redact(original)
                if data["message"] != original:
                    logger.debug(
                        "PII redacted in session %s", data.get("session_id", "?")
                    )
            return json.dumps(data).encode()
        except Exception:
            logger.exception("PII middleware body parse error — passing through unmodified")
            return body
