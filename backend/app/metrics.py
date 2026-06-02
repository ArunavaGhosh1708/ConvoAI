"""
Prometheus instrumentation for FastAPI.

Exposes /metrics endpoint (Prometheus text format).
Adds per-route latency histograms, request counts, and escalation counter.

Requires: prometheus-fastapi-instrumentator
"""

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Custom business counters (registered globally so they survive multiple calls)
_initialized = False
_escalation_counter = None
_rag_cache_hit_counter = None
_rag_cache_miss_counter = None


def _build_counters():
    global _escalation_counter, _rag_cache_hit_counter, _rag_cache_miss_counter
    try:
        from prometheus_client import Counter
        _escalation_counter = Counter(
            "convoai_escalations_total",
            "Total number of conversations escalated to human agents",
            ["channel"],
        )
        _rag_cache_hit_counter = Counter(
            "convoai_rag_cache_hits_total",
            "Redis cache hits for conversation history",
        )
        _rag_cache_miss_counter = Counter(
            "convoai_rag_cache_misses_total",
            "Redis cache misses for conversation history",
        )
    except ImportError:
        logger.warning("prometheus_client not installed — custom counters disabled")


def increment_escalation(channel: str = "chat") -> None:
    if _escalation_counter is not None:
        _escalation_counter.labels(channel=channel).inc()


def increment_rag_cache_hit() -> None:
    if _rag_cache_hit_counter is not None:
        _rag_cache_hit_counter.inc()


def increment_rag_cache_miss() -> None:
    if _rag_cache_miss_counter is not None:
        _rag_cache_miss_counter.inc()


def setup_metrics(app: FastAPI, expose_endpoint: str = "/metrics") -> None:
    """Attach prometheus-fastapi-instrumentator to the app."""
    global _initialized
    if _initialized:
        return
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            excluded_handlers=["/metrics", "/api/v1/health"],
        ).instrument(app).expose(app, endpoint=expose_endpoint, include_in_schema=False)

        _build_counters()
        _initialized = True
        logger.info("Prometheus metrics exposed at %s", expose_endpoint)
    except ImportError:
        logger.warning(
            "prometheus-fastapi-instrumentator not installed — metrics disabled. "
            "Add it to requirements.txt to enable."
        )
