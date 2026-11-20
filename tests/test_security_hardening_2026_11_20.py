"""Regression tests for security hardening fixes (2026-11-20).

Covers:
1. api/routes/messages.py: reject spoofable validator metadata keys in prod.
2. gate_coordinator.py: fail closed on non-finite, bool, and non-numeric impact_score.
3. bus/messaging.py: unconditional fail-closed DEGRADED fallback on processor exceptions.
4. builder.py: _NoOpIntentClassifier.classify_async compatibility without weakening gates.

Constitutional Hash: 608508a9bd224290
"""

from __future__ import annotations

import builtins
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from enhanced_agent_bus._compat.security.auth import UserClaims, get_current_user
from enhanced_agent_bus.api.dependencies import get_agent_bus
from enhanced_agent_bus.api.message_lifecycle import InMemoryMessageStatusStore
from enhanced_agent_bus.api.rate_limiting import limiter
from enhanced_agent_bus.api.routes.messages import router
from enhanced_agent_bus.bus.messaging import MessageHandler
from enhanced_agent_bus.config import BusConfiguration
from enhanced_agent_bus.gate_coordinator import GateCoordinator
from enhanced_agent_bus.models import AgentMessage, MessageStatus, MessageType, Priority


class _FakeBus:
    async def process(self, message: object) -> SimpleNamespace:
        _ = message
        return SimpleNamespace(is_valid=True)


def _make_messages_client() -> TestClient:
    limiter.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.state.message_status_store = InMemoryMessageStatusStore()
    app.state.failed_tasks = []
    app.include_router(router)

    async def _user() -> UserClaims:
        return UserClaims(sub="agent-user", tenant_id="tenant-a", roles=["agent"])

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_agent_bus] = lambda: _FakeBus()
    return TestClient(app)


def _message_payload(metadata: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "content": "execute governed task",
        "message_type": "governance_request",
        "sender": "agent-origin",
        "recipient": "agent-exec",
        "tenant_id": "tenant-a",
    }
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


def _make_gate_coordinator() -> GateCoordinator:
    return GateCoordinator(
        require_independent_validator=True,
        independent_validator_threshold=0.8,
        security_scanner=SimpleNamespace(
            scan=AsyncMock(return_value=None),
            detect_prompt_injection=MagicMock(return_value=None),
        ),
        record_agent_workflow_event=MagicMock(),
        increment_failed_count=MagicMock(),
        advisory_blocked_types=frozenset({"command", "governance_request", "task_request"}),
    )


def _make_handler(processor: object) -> MessageHandler:
    return MessageHandler(
        processor=processor,  # type: ignore[arg-type]
        router_component=MagicMock(),
        registry_manager=MagicMock(),
        governance=MagicMock(),
        validator=MagicMock(),
        message_queue=MagicMock(),
        deliberation_queue=None,
        metering_manager=MagicMock(),
        kafka_bus=None,
        metrics={},
        config={},
    )


# ---------------------------------------------------------------------------
# 1. api/routes/messages.py: reject spoofable validator metadata in prod
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("validated_by_agent", "agent-validator"),
        ("independent_validator_id", "indep-validator-01"),
        ("validation_stage", "independent"),
        ("prevalidated", True),
        ("prevalidated_result", {"is_valid": True}),
    ],
)
def test_send_message_rejects_spoofable_metadata_in_prod(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: object,
) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    client = _make_messages_client()

    response = client.post("/api/v1/messages", json=_message_payload({key: value}))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "verifiable receipt" in detail
    assert key in detail


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"validated_by_agent": ""},
        {"independent_validator_id": "   "},
        {"validation_stage": None},
        {"prevalidated": False},
        {"prevalidated_result": {}},
        {"benign_trace": "trace-123"},
    ],
)
def test_send_message_allows_empty_or_non_spoofable_metadata_in_prod(
    monkeypatch: pytest.MonkeyPatch,
    metadata: dict[str, object],
) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    client = _make_messages_client()

    response = client.post("/api/v1/messages", json=_message_payload(metadata))

    assert response.status_code == 202


def test_send_message_allows_spoofable_metadata_in_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    client = _make_messages_client()

    response = client.post(
        "/api/v1/messages",
        json=_message_payload({"validated_by_agent": "dev-validator", "prevalidated": True}),
    )

    assert response.status_code == 202


# ---------------------------------------------------------------------------
# 2. gate_coordinator.py: fail closed on invalid impact_score values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_score",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        False,
        "0.1",
        "high",
        object(),
    ],
)
def test_requires_independent_validation_fails_closed_on_invalid_impact_score(
    bad_score: object,
) -> None:
    coordinator = _make_gate_coordinator()
    msg = SimpleNamespace(
        impact_score=bad_score,
        message_type=MessageType.QUERY,
        from_agent="origin-agent",
        metadata={},
    )

    assert coordinator.requires_independent_validation(msg) is True  # type: ignore[arg-type]


def test_enforce_independent_validator_gate_rejects_nan_impact_score_without_validator() -> None:
    coordinator = _make_gate_coordinator()
    msg = AgentMessage(
        content={"q": "status"},
        message_type=MessageType.QUERY,
        from_agent="origin-agent",
        to_agent="target-agent",
    )
    msg.impact_score = math.nan

    result = coordinator.enforce_independent_validator_gate(msg)

    assert result is not None
    assert result.is_valid is False
    assert result.metadata.get("rejection_reason") == "independent_validator_missing"


def test_requires_independent_validation_preserves_none_and_numeric_thresholds() -> None:
    coordinator = _make_gate_coordinator()
    msg_none = SimpleNamespace(impact_score=None, message_type=MessageType.QUERY)
    msg_low = SimpleNamespace(impact_score=0.5, message_type=MessageType.QUERY)
    msg_high = SimpleNamespace(impact_score=0.8, message_type=MessageType.QUERY)

    assert coordinator.requires_independent_validation(msg_none) is False  # type: ignore[arg-type]
    assert coordinator.requires_independent_validation(msg_low) is False  # type: ignore[arg-type]
    assert coordinator.requires_independent_validation(msg_high) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. bus/messaging.py: fail closed unconditionally on processor exception
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spoofed_metadata",
    [
        {},
        {"prevalidated": True},
        {"prevalidated_result": {"is_valid": True}},
        {"validated_by_agent": "validator-1"},
        {"independent_validator_id": "indep-1"},
    ],
)
async def test_decide_message_governance_fails_closed_on_processor_exception(
    spoofed_metadata: dict[str, object],
) -> None:
    processor = MagicMock()
    processor.process = AsyncMock(side_effect=RuntimeError("processor offline"))
    handler = _make_handler(processor)
    msg = AgentMessage(
        content={"action": "deploy"},
        message_type=MessageType.GOVERNANCE_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        metadata=dict(spoofed_metadata),
    )

    decision = await handler.decide_message_governance(msg)

    assert decision.allow_delivery is False
    assert decision.result.is_valid is False
    assert decision.result.decision == "DENY"
    assert decision.result.status == MessageStatus.FAILED
    assert decision.result.metadata == {
        "governance_mode": "DEGRADED",
        "fallback_reason": "processor offline",
    }


# ---------------------------------------------------------------------------
# 4. builder.py: _NoOpIntentClassifier.classify_async compatibility
# ---------------------------------------------------------------------------


async def test_builder_noop_intent_classifier_classify_async_and_orchestrator_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import enhanced_agent_bus.builder as builder_mod
    from enhanced_agent_bus.verification_orchestrator import VerificationOrchestrator

    monkeypatch.setattr(builder_mod, "_cached_sdpc", None)
    real_import = builtins.__import__

    def _block_sdpc(name: str, *args: object, **kwargs: object) -> object:
        if "intent_classifier" in name or "sdpc" in name:
            raise ImportError(f"blocked {name}")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    with patch("builtins.__import__", side_effect=_block_sdpc):
        sdpc = builder_mod.build_sdpc_verifiers(BusConfiguration(enable_maci=False))

    intent_default = await sdpc.intent_classifier.classify_async("hello world")  # type: ignore[attr-defined]
    intent_ctx = await sdpc.intent_classifier.classify_async("hello", context={"k": "v"})  # type: ignore[attr-defined]

    assert intent_default.value == "unknown"
    assert intent_ctx.value == "unknown"
    assert intent_default == "unknown"
    assert sdpc.IntentType.FACTUAL.value == "factual"
    assert sdpc.IntentType.REASONING.value == "reasoning"

    # Wire builder fallback into VerificationOrchestrator and verify high-impact PACAR gate
    # still executes and fails closed (does not mark sdpc_pacar_valid=True).
    orchestrator = VerificationOrchestrator(config=BusConfiguration(enable_maci=False))
    orchestrator.intent_classifier = sdpc.intent_classifier
    orchestrator.asc_verifier = sdpc.asc_verifier
    orchestrator.graph_check = sdpc.graph_check
    orchestrator.pacar_verifier = sdpc.pacar_verifier
    orchestrator.evolution_controller = sdpc.evolution_controller
    orchestrator.ampo_engine = sdpc.ampo_engine
    orchestrator._IntentType = sdpc.IntentType

    task_msg = AgentMessage(
        content={"task": "sensitive task"},
        message_type=MessageType.TASK_REQUEST,
        from_agent="agent-a",
        to_agent="agent-b",
        impact_score=0.95,
    )
    verification = await orchestrator.verify(task_msg, "sensitive task")
    assert verification.sdpc_metadata.get("sdpc_pacar_valid") is False
