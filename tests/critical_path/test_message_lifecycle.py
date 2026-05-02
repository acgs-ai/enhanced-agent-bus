"""Critical-path tests for accepted-vs-approved message semantics."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enhanced_agent_bus._compat.security.auth import UserClaims, get_current_user
from enhanced_agent_bus.api.dependencies import get_agent_bus
from enhanced_agent_bus.api.message_lifecycle import InMemoryMessageStatusStore
from enhanced_agent_bus.api.routes.messages import router


@dataclass
class _ProcessResult:
    is_valid: bool


class _FakeBus:
    def __init__(self, *, valid: bool) -> None:
        self.valid = valid

    async def process(self, message: object) -> _ProcessResult:
        return _ProcessResult(is_valid=self.valid)


def _app(*, valid: bool = True) -> FastAPI:
    app = FastAPI()
    app.state.message_status_store = InMemoryMessageStatusStore()
    app.state.failed_tasks = []
    app.include_router(router)

    async def _user() -> UserClaims:
        return UserClaims(sub="agent-user", tenant_id="tenant-a", roles=["agent"])

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_agent_bus] = lambda: _FakeBus(valid=valid)
    return app


def _payload() -> dict[str, object]:
    return {
        "content": "govern this action",
        "message_type": "governance_request",
        "sender": "agent-origin",
        "recipient": "agent-exec",
        "tenant_id": "tenant-a",
    }


def test_async_submit_returns_accepted_for_processing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    client = TestClient(_app(valid=True))

    response = client.post("/api/v1/messages", json=_payload())

    assert response.status_code == 202
    assert response.json()["status"] == "accepted_for_processing"


def test_valid_message_becomes_governance_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    client = TestClient(_app(valid=True))

    submit = client.post("/api/v1/messages", json=_payload())
    message_id = submit.json()["message_id"]
    status = client.get(f"/api/v1/messages/{message_id}/status")

    assert status.status_code == 200
    assert status.json()["status"] == "governance_approved"


def test_invalid_message_becomes_governance_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    client = TestClient(_app(valid=False))

    submit = client.post("/api/v1/messages", json=_payload())
    message_id = submit.json()["message_id"]
    status = client.get(f"/api/v1/messages/{message_id}/status")

    assert status.status_code == 200
    assert status.json()["status"] == "governance_rejected"


def test_sync_mode_returns_rejection_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    client = TestClient(_app(valid=False))

    response = client.post(
        "/api/v1/messages?mode=validate_and_route",
        json=_payload(),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "governance_rejected"


def test_spoofed_validator_headers_rejected_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    client = TestClient(_app(valid=True))

    response = client.post(
        "/api/v1/messages",
        json=_payload(),
        headers={"X-Validated-By-Agent": "agent-validator"},
    )

    assert response.status_code == 400
    assert "verifiable receipt" in response.json()["detail"]


def test_tenant_a_cannot_access_tenant_b_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    app = _app(valid=True)
    client = TestClient(app)

    app.state.message_status_store.record(
        tenant_id="tenant-b",
        message_id="00000000-0000-0000-0000-000000000001",
        state="governance_approved",
    )
    response = client.get("/api/v1/messages/00000000-0000-0000-0000-000000000001/status")

    assert response.status_code == 404
