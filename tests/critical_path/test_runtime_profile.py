"""Critical-path tests for runtime profile fail-closed behavior."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from enhanced_agent_bus.api import app as app_module
from enhanced_agent_bus.api.runtime_profile import allow_fallback, current_profile


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
