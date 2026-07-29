"""Critical-path tests for runtime profile fail-closed behavior."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from enhanced_agent_bus._compat import _degraded
from enhanced_agent_bus.api import app as app_module
from enhanced_agent_bus.api.runtime_profile import (
    allow_fallback,
    current_profile,
    require_no_degraded_dependencies,
)


class _FailingRedis:
    def ping(self) -> None:
        raise ConnectionError("redis unavailable")


class _HealthyRedis:
    async def ping(self) -> bool:
        return True


def test_profile_defaults_to_dev_for_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EAB_PROFILE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "test")

    assert current_profile() == "dev"
    assert allow_fallback("governance_state") is True


def test_prod_disallows_in_memory_governance_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")

    assert allow_fallback("governance_state") is False


@pytest.mark.asyncio
async def test_prod_unavailable_redis_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    app = FastAPI()
    app.state.governance_redis_client = _FailingRedis()

    with pytest.raises(RuntimeError, match="Redis readiness"):
        await app_module._verify_governance_redis_ready(app)


@pytest.mark.asyncio
async def test_prod_missing_auth_secret_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    for name in ("ACGS2_SERVICE_SECRET", "JWT_SECRET", "JWT_SECRET_KEY", "EAB_AUTH_SECRET"):
        monkeypatch.delenv(name, raising=False)
    app = FastAPI()
    app.state.governance_redis_client = _HealthyRedis()

    with pytest.raises(RuntimeError, match="auth_secret"):
        await app_module._verify_startup_dependencies(app)


@pytest.mark.asyncio
async def test_prod_mock_policy_backend_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("ACGS2_SERVICE_SECRET", "test-secret")
    monkeypatch.setenv("POLICY_REGISTRY_URL", "http://mock-policy")
    app = FastAPI()
    app.state.governance_redis_client = _HealthyRedis()

    with pytest.raises(RuntimeError, match="policy_backend_non_mock"):
        await app_module._verify_startup_dependencies(app)


def test_degraded_security_shim_blocks_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    """A security-tier fallback must refuse a production start by name."""

    monkeypatch.setenv("EAB_PROFILE", "prod")

    with pytest.raises(RuntimeError, match="non_degraded_dependencies"):
        require_no_degraded_dependencies()


def test_degraded_observability_shim_does_not_block_prod(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only security and governance tiers are fatal; observability is reportable."""

    monkeypatch.setenv("EAB_PROFILE", "prod")
    snapshot = _degraded.active()
    _degraded.clear()
    _degraded.register("metrics.noop", "observability")
    try:
        require_no_degraded_dependencies()
    finally:
        _degraded.clear()
        for name, tier in snapshot.items():
            _degraded.register(name, tier)  # type: ignore[arg-type]


def test_no_degradations_allows_prod_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """With every dependency real, the gate is a no-op."""

    monkeypatch.setenv("EAB_PROFILE", "prod")
    snapshot = _degraded.active()
    _degraded.clear()
    try:
        require_no_degraded_dependencies()
    finally:
        for name, tier in snapshot.items():
            _degraded.register(name, tier)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_degradation_gate_is_wired_into_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proof of wiring: the gate runs from `_verify_startup_dependencies`.

    A passing unit test on `require_no_degraded_dependencies` alone would not
    show that startup calls it, so this drives the real startup path with every
    preceding gate satisfied.
    """

    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("ACGS2_SERVICE_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "_verify_policy_backend_ready", _noop)
    monkeypatch.setattr(app_module, "_verify_audit_backend_ready", _noop)
    app = FastAPI()
    app.state.governance_redis_client = _HealthyRedis()

    with pytest.raises(RuntimeError, match="non_degraded_dependencies"):
        await app_module._verify_startup_dependencies(app)


async def _noop() -> None:
    """Stand-in for a satisfied startup gate."""
