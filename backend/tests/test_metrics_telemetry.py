"""Unit tests for metrics, telemetry, and secrets modules."""

import pytest
from unittest.mock import MagicMock, patch


# ===========================================================================
# metrics.py
# ===========================================================================

def test_setup_metrics_graceful_when_package_missing():
    from fastapi import FastAPI
    app = FastAPI()

    with patch.dict("sys.modules", {"prometheus_fastapi_instrumentator": None}):
        import importlib
        import app.metrics as metrics_mod
        # Reset initialized flag for isolated test
        metrics_mod._initialized = False
        metrics_mod.setup_metrics(app)   # should not raise


def test_increment_escalation_noop_when_counter_none():
    import app.metrics as metrics_mod
    original = metrics_mod._escalation_counter
    metrics_mod._escalation_counter = None
    metrics_mod.increment_escalation("chat")   # must not raise
    metrics_mod._escalation_counter = original


def test_increment_rag_counters_noop_when_none():
    import app.metrics as metrics_mod
    original_hit  = metrics_mod._rag_cache_hit_counter
    original_miss = metrics_mod._rag_cache_miss_counter
    metrics_mod._rag_cache_hit_counter = None
    metrics_mod._rag_cache_miss_counter = None
    metrics_mod.increment_rag_cache_hit()
    metrics_mod.increment_rag_cache_miss()
    metrics_mod._rag_cache_hit_counter = original_hit
    metrics_mod._rag_cache_miss_counter = original_miss


def test_increment_escalation_calls_counter_when_set():
    import app.metrics as metrics_mod
    mock_counter = MagicMock()
    original = metrics_mod._escalation_counter
    metrics_mod._escalation_counter = mock_counter
    metrics_mod.increment_escalation("voice")
    mock_counter.labels.assert_called_with(channel="voice")
    mock_counter.labels.return_value.inc.assert_called_once()
    metrics_mod._escalation_counter = original


# ===========================================================================
# telemetry.py
# ===========================================================================

def test_setup_telemetry_noop_without_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    from fastapi import FastAPI
    from app.telemetry import setup_telemetry
    setup_telemetry(FastAPI())  # must not raise


def test_setup_telemetry_graceful_when_packages_missing(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel:4317")
    from fastapi import FastAPI

    with patch.dict("sys.modules", {
        "opentelemetry": None,
        "opentelemetry.sdk": None,
    }):
        from app.telemetry import setup_telemetry
        setup_telemetry(FastAPI())   # must not raise


# ===========================================================================
# secrets.py
# ===========================================================================

def test_get_secret_returns_env_var(monkeypatch):
    import os
    monkeypatch.setenv("MY_TEST_SECRET", "supersecret")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    import importlib
    import app.secrets as secrets_mod
    secrets_mod._GCP_PROJECT_ID = ""   # ensure no GCP path taken

    result = secrets_mod.get_secret("MY_TEST_SECRET")
    assert result == "supersecret"


def test_get_secret_returns_default_when_not_set(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    import app.secrets as secrets_mod
    secrets_mod._GCP_PROJECT_ID = ""

    result = secrets_mod.get_secret("NONEXISTENT_SECRET", default="fallback")
    assert result == "fallback"


def test_get_secret_raises_when_nothing_available(monkeypatch):
    monkeypatch.delenv("TRULY_MISSING", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    import app.secrets as secrets_mod
    secrets_mod._GCP_PROJECT_ID = ""

    with pytest.raises(RuntimeError, match="TRULY_MISSING"):
        secrets_mod.get_secret("TRULY_MISSING")


def test_preload_secrets_returns_dict(monkeypatch):
    monkeypatch.setenv("KEY_A", "val_a")
    monkeypatch.setenv("KEY_B", "val_b")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

    import app.secrets as secrets_mod
    secrets_mod._GCP_PROJECT_ID = ""

    result = secrets_mod.preload_secrets(["KEY_A", "KEY_B"])
    assert result == {"KEY_A": "val_a", "KEY_B": "val_b"}
