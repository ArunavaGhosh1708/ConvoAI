"""Unit tests for the LLM circuit breaker."""

import pytest

from app.agent.circuit_breaker import CircuitBreaker, CircuitBreakerOpen


def make_breaker(**kwargs):
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=60.0,
        success_threshold=2,
        **kwargs,
    )


def test_initial_state_is_closed():
    cb = make_breaker()
    assert cb.state == "CLOSED"


def test_before_call_passes_when_closed():
    cb = make_breaker()
    cb.before_call()  # should not raise


def test_opens_after_failure_threshold():
    cb = make_breaker()
    for _ in range(3):
        cb.on_failure()
    assert cb.state == "OPEN"


def test_open_rejects_calls():
    cb = make_breaker()
    for _ in range(3):
        cb.on_failure()
    with pytest.raises(CircuitBreakerOpen):
        cb.before_call()


def test_success_resets_failure_count_when_closed():
    cb = make_breaker()
    cb.on_failure()
    cb.on_failure()
    cb.on_success()        # resets counter
    cb.on_failure()        # only 1 failure now — should not open
    assert cb.state == "CLOSED"


def test_transitions_to_half_open_after_timeout(monkeypatch):
    import time
    cb = make_breaker(recovery_timeout=0.0)
    for _ in range(3):
        cb.on_failure()
    assert cb.state == "OPEN"

    # Advance time past recovery_timeout
    monkeypatch.setattr(time, "monotonic", lambda: 9999.0)
    cb.before_call()  # should not raise — transitions to HALF_OPEN
    assert cb.state == "HALF_OPEN"


def test_half_open_closes_after_success_threshold(monkeypatch):
    import time
    cb = make_breaker(recovery_timeout=0.0, success_threshold=2)
    for _ in range(3):
        cb.on_failure()
    monkeypatch.setattr(time, "monotonic", lambda: 9999.0)
    cb.before_call()  # → HALF_OPEN

    cb.on_success()
    assert cb.state == "HALF_OPEN"
    cb.on_success()
    assert cb.state == "CLOSED"


def test_half_open_reopens_on_failure(monkeypatch):
    import time
    cb = make_breaker(recovery_timeout=0.0)
    for _ in range(3):
        cb.on_failure()
    monkeypatch.setattr(time, "monotonic", lambda: 9999.0)
    cb.before_call()  # → HALF_OPEN
    cb.on_failure()   # → OPEN again
    assert cb.state == "OPEN"
