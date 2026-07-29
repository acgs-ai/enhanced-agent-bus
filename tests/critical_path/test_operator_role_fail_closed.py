"""Critical-path tests: the operator-override seam must fail closed.

`_compat/security/rbac.py` always imports, so the `except ImportError` guard in
``require_operator_role`` only fires if the fallback *raises*. These tests drive
the dependency through the router — a direct call would prove the raise, not the
HTTP outcome — and assert the strict path is reached under a production profile.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from enhanced_agent_bus._compat import _degraded
from enhanced_agent_bus._compat.security.rbac import RBACUnavailableError, validate_operator_token
from enhanced_agent_bus.api.routes.agent_health import require_operator_role


@pytest.fixture
def operator_app() -> FastAPI:
    """A minimal app exposing one route behind ``require_operator_role``."""

    app = FastAPI()

    @app.get("/probe")
    async def probe(operator: str = Depends(require_operator_role)) -> dict[str, str]:
        return {"operator": operator}

    return app


def test_rbac_fallback_registers_a_security_degradation() -> None:
    """The shim must announce that it substituted a fallback."""

    assert _degraded.active().get("security.rbac") == "security"
    assert "security.rbac" in _degraded.active_blocking()


@pytest.mark.asyncio
async def test_validate_operator_token_refuses_to_mint_an_identity() -> None:
    """No backend means no identity — not a dev-shaped placeholder identity."""

    with pytest.raises(RBACUnavailableError):
        await validate_operator_token("")
    with pytest.raises(RBACUnavailableError):
        await validate_operator_token("some-token")


def test_rbac_unavailable_error_is_an_import_error() -> None:
    """Callers guarding the seam with ``except ImportError`` must catch it."""

    assert issubclass(RBACUnavailableError, ImportError)


def test_operator_route_refuses_unauthenticated_request_in_prod(
    operator_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No Authorization header under EAB_PROFILE=prod must not yield an operator."""

    monkeypatch.setenv("EAB_PROFILE", "prod")
    response = TestClient(operator_app).get("/probe")

    assert response.status_code in {401, 503}, response.text
    assert "operator" not in response.json()


def test_operator_route_refuses_bearer_token_in_prod(
    operator_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An arbitrary bearer token must not be accepted as an operator either."""

    monkeypatch.setenv("EAB_PROFILE", "prod")
    response = TestClient(operator_app).get(
        "/probe", headers={"Authorization": "Bearer anything-at-all"}
    )

    assert response.status_code == 503, response.text


def test_health_reports_active_degradations() -> None:
    """An operator must be able to see the runtime is degraded without reading logs."""

    from enhanced_agent_bus.api.routes.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)
    payload = TestClient(app).get("/health").json()

    assert payload["degraded_dependencies"].get("security.rbac") == "security"
    assert payload["status"] == "degraded"


def test_prod_profile_beats_dev_environment_variable(
    operator_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EAB_PROFILE is authoritative: ENVIRONMENT=test must not open the dev path."""

    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("ENVIRONMENT", "test")
    response = TestClient(operator_app).get(
        "/probe", headers={"Authorization": "Bearer anything-at-all"}
    )

    assert response.status_code == 503, response.text
