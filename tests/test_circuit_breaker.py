"""Circuit breaker state transition tests (US-001 Cat 1).

Exercises the documented state machine of
``enhanced_agent_bus.circuit_breaker.breaker.ServiceCircuitBreaker``:

    CLOSED -> OPEN: consecutive failures >= threshold
    OPEN -> HALF_OPEN: after timeout expires
    HALF_OPEN -> CLOSED: after half_open_requests successes
    HALF_OPEN -> OPEN: on any failure during half-open
"""

from __future__ import annotations

import asyncio

import pytest

from enhanced_agent_bus.circuit_breaker.breaker import ServiceCircuitBreaker
from enhanced_agent_bus.circuit_breaker.config import ServiceCircuitConfig
from enhanced_agent_bus.circuit_breaker.enums import (
    CircuitState,
    FallbackStrategy,
    ServiceSeverity,
)


def _make_breaker(
    *,
    threshold: int = 2,
    timeout: float = 0.1,
    half_open: int = 2,
) -> ServiceCircuitBreaker:
    cfg = ServiceCircuitConfig(
        name="test_service",
        failure_threshold=threshold,
        timeout_seconds=timeout,
        half_open_requests=half_open,
        fallback_strategy=FallbackStrategy.FAIL_CLOSED,
        severity=ServiceSeverity.MEDIUM,
    )
    return ServiceCircuitBreaker(cfg)


@pytest.mark.asyncio
async def test_starts_closed_and_allows_execution() -> None:
    cb = _make_breaker()
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute() is True


@pytest.mark.asyncio
async def test_closed_to_open_on_threshold_failures() -> None:
    cb = _make_breaker(threshold=2)

    await cb.record_failure(error_type="timeout")
    assert cb.state == CircuitState.CLOSED

    await cb.record_failure(error_type="timeout")
    assert cb.state == CircuitState.OPEN
    # When OPEN and before the timeout expires, execution is denied
    assert await cb.can_execute() is False


@pytest.mark.asyncio
async def test_open_transitions_to_half_open_after_timeout() -> None:
    cb = _make_breaker(threshold=1, timeout=0.05)
    await cb.record_failure(error_type="boom")
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.15)
    # Probe call after timeout should move the circuit into HALF_OPEN
    assert await cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_to_closed_after_successes() -> None:
    cb = _make_breaker(threshold=1, timeout=0.05, half_open=2)
    await cb.record_failure(error_type="boom")
    await asyncio.sleep(0.15)
    await cb.can_execute()  # triggers transition to HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_success()
    # Still half-open until the configured number of successes is reached
    assert cb.state == CircuitState.HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_to_open_on_failure() -> None:
    cb = _make_breaker(threshold=1, timeout=0.05, half_open=3)
    await cb.record_failure(error_type="boom")
    await asyncio.sleep(0.15)
    await cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    await cb.record_failure(error_type="still-broken")
    assert cb.state == CircuitState.OPEN
