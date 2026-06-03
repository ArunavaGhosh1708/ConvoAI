"""
Simple in-process circuit breaker for the OpenAI LLM API.

States:
  CLOSED    — normal operation; failures are counted.
  OPEN      — fast-fail; no calls forwarded until the cooldown expires.
  HALF_OPEN — one probe call allowed; resets to CLOSED on success,
              back to OPEN on failure.

All state is process-local (no Redis), which is intentional: each Cloud Run
instance manages its own breaker so a single flaky instance does not affect
the others, and recovery probes are naturally distributed.
"""

import logging
import time
from enum import Enum, auto
from threading import Lock

logger = logging.getLogger(__name__)


class _State(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int   = 5,
        recovery_timeout:  float = 30.0,
        success_threshold: int   = 2,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout  = recovery_timeout
        self._success_threshold = success_threshold

        self._state            = _State.CLOSED
        self._failure_count    = 0
        self._success_count    = 0
        self._opened_at: float = 0.0
        self._lock             = Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def before_call(self) -> None:
        """Call before forwarding a request. Raises CircuitBreakerOpen if OPEN."""
        with self._lock:
            if self._state == _State.OPEN:
                if time.monotonic() - self._opened_at >= self._recovery_timeout:
                    logger.info("Circuit breaker → HALF_OPEN (probe allowed)")
                    self._state         = _State.HALF_OPEN
                    self._success_count = 0
                else:
                    raise CircuitBreakerOpen(
                        "LLM API circuit breaker is OPEN — request rejected"
                    )

    def on_success(self) -> None:
        with self._lock:
            if self._state == _State.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._success_threshold:
                    logger.info("Circuit breaker → CLOSED after %d successes", self._success_count)
                    self._state         = _State.CLOSED
                    self._failure_count = 0
            elif self._state == _State.CLOSED:
                self._failure_count = 0

    def on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == _State.HALF_OPEN or self._failure_count >= self._failure_threshold:
                logger.warning(
                    "Circuit breaker → OPEN (failures=%d)", self._failure_count
                )
                self._state      = _State.OPEN
                self._opened_at  = time.monotonic()
                self._failure_count = 0

    @property
    def state(self) -> str:
        return self._state.name


# Module-level singleton — one breaker per process/instance.
llm_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    success_threshold=2,
)
