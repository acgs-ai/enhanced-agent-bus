"""Critical-path route authorization tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enhanced_agent_bus.api.dependencies import get_agent_bus
from enhanced_agent_bus.api.routes.messages import router


def test_mutating_message_route_requires_auth_in_prod(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_agent_bus] = lambda: {"status": "mock"}
    client = TestClient(app)

    response = client.post(
        "/api/v1/messages",
        json={
            "content": "govern this action",
            "message_type": "governance_request",
            "sender": "agent-origin",
            "tenant_id": "tenant-a",
        },
    )

    assert response.status_code == 401
