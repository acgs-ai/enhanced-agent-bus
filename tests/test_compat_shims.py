"""Smoke tests for enhanced_agent_bus._compat shims (US-001 Cat 1).

Verifies the shim modules expose their canonical names in both the
real-import path and the fallback-stub path. These tests must pass whether
or not the upstream ``src.core.shared.*`` modules are present in the
environment.
"""

from __future__ import annotations

import pytest


def test_constants_shim_exports_hash_and_enums() -> None:
    from enhanced_agent_bus._compat import constants

    assert isinstance(constants.CONSTITUTIONAL_HASH, str)
    assert len(constants.CONSTITUTIONAL_HASH) >= 16
    assert constants.RiskTier.LOW.value == "low"
    assert constants.RiskTier.MEDIUM.value == "medium"
    assert constants.RiskTier.HIGH.value == "high"

    # classify_risk_tier must honour the documented thresholds
    assert constants.classify_risk_tier(0.0) == constants.RiskTier.LOW
    assert constants.classify_risk_tier(0.5) == constants.RiskTier.MEDIUM
    assert constants.classify_risk_tier(0.99) == constants.RiskTier.HIGH


def test_constants_shim_maci_role_parse() -> None:
    from enhanced_agent_bus._compat.constants import MACIRole

    assert MACIRole.parse("EXECUTIVE") == MACIRole.EXECUTIVE
    assert MACIRole.parse("legislative") == MACIRole.LEGISLATIVE
    assert MACIRole.parse(MACIRole.JUDICIAL) == MACIRole.JUDICIAL


def test_errors_shim_exports_base_hierarchy() -> None:
    from enhanced_agent_bus._compat.errors import (
        ACGSBaseError,
        ConstitutionalViolationError,
        MACIEnforcementError,
        RateLimitExceededError,
        TenantIsolationError,
        ValidationError,
    )

    for cls in (
        ConstitutionalViolationError,
        MACIEnforcementError,
        RateLimitExceededError,
        TenantIsolationError,
        ValidationError,
    ):
        assert issubclass(cls, ACGSBaseError)

    err = ConstitutionalViolationError("boom", violations=["rule-1"])
    assert err.violations == ["rule-1"]
    payload = err.to_dict()
    assert payload["error"] == "CONSTITUTIONAL_VIOLATION"
    assert payload["constitutional_hash"]


def test_types_shim_exports_core_type_aliases() -> None:
    from enhanced_agent_bus._compat import types as compat_types

    # CONSTITUTIONAL_HASH is re-exported; other names are best-effort
    assert hasattr(compat_types, "CONSTITUTIONAL_HASH")


def test_resilience_retry_decorator_runs_once_when_stub() -> None:
    from enhanced_agent_bus._compat.resilience.retry import RetryConfig, retry

    # RetryConfig accepts arbitrary kwargs without error
    cfg = RetryConfig(max_retries=2, base_delay=0.01)
    assert cfg is not None

    calls = {"n": 0}

    @retry(max_retries=1)
    def _fn() -> int:
        calls["n"] += 1
        return 42

    assert _fn() == 42
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_resilience_retry_async_wrapper_runs_once_when_stub() -> None:
    from enhanced_agent_bus._compat.resilience.retry import retry

    calls = {"n": 0}

    @retry(max_retries=1)
    async def _afn() -> str:
        calls["n"] += 1
        return "ok"

    assert await _afn() == "ok"
    assert calls["n"] == 1
