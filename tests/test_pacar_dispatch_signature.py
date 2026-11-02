"""
Regression: PACAR dispatch from MessageProcessor.process() must match the real
PACARVerifier signatures, and PACAR verdicts must be enforced fail-closed.

verification_orchestrator previously called ``PACARVerifier.verify(..., session_id=...)``,
which raised TypeError for every TASK_REQUEST / impact>0.8 message; the processor then
retried and rejected with max_retries_exceeded. Earlier tests hid this by replacing
``verify`` with a bare AsyncMock that accepts any kwargs. These tests keep the real
method signatures and stub only the LLM assistant and session store underneath.

The SDPC verifiers are a process-wide singleton shared by every MessageProcessor, so
every patch goes through ``monkeypatch`` and is restored after each test.

Constitutional Hash: 608508a9bd224290
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from enhanced_agent_bus.message_processor import MessageProcessor
from enhanced_agent_bus.models import AgentMessage, MessageType
from enhanced_agent_bus.sdpc.pacar_manager import PACARManager
from enhanced_agent_bus.sdpc.pacar_verifier import PACARVerifier


class _FakeManager:
    def __init__(self) -> None:
        self.added: list[tuple[str, object, str]] = []

    async def get_state(self, session_id: str) -> SimpleNamespace:
        return SimpleNamespace(messages=[])

    async def add_message(self, session_id, role, content, metadata=None) -> None:
        self.added.append((session_id, role, content))


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


def _approving_assistant() -> SimpleNamespace:
    return SimpleNamespace(
        analyze_message_impact=AsyncMock(
            return_value={"risk_level": "low", "confidence": 0.9, "reasoning": ["ok"]}
        ),
        ainvoke_multi_turn=AsyncMock(
            return_value={
                "recommended_decision": "approve",
                "confidence": 0.8,
                "reasoning": ["multi-turn ok"],
            }
        ),
    )


@pytest.fixture
def pacar(monkeypatch: pytest.MonkeyPatch) -> tuple[MessageProcessor, PACARVerifier]:
    processor = MessageProcessor(
        enable_maci=False
    )  # test-only: MACI off — testing SDPC/PACAR dispatch independently
    verifier = processor.pacar_verifier
    if not isinstance(verifier, PACARVerifier):
        pytest.fail("SDPC unavailable: processor uses no-op PACAR verifier")
    monkeypatch.setattr(verifier, "assistant", _approving_assistant())
    monkeypatch.setattr(verifier, "manager", _FakeManager())
    monkeypatch.setattr(verifier, "redis_client", None)
    monkeypatch.setattr(verifier, "audit_client", None)
    return processor, verifier


def _assert_pacar_blocked(result) -> None:
    assert result.is_valid is False
    assert result.decision == "DENY"
    assert result.metadata.get("sdpc_pacar_valid") is False
    assert result.metadata.get("rejection_reason") == "pacar_verification_failed"
    assert "PACAR verification rejected message" in result.errors


def _task_request(**extra: object) -> AgentMessage:
    return AgentMessage(
        content={"task": "Summarize quarterly governance metrics"},
        message_type=MessageType.TASK_REQUEST,
        from_agent="admin-agent",
        to_agent="analysis-agent",
        **extra,
    )


async def test_task_request_without_session_uses_single_turn_verify(pacar) -> None:
    processor, verifier = pacar

    result = await processor.process(_task_request())

    assert result.is_valid, result.errors
    assert result.metadata.get("sdpc_pacar_valid") is True
    assert result.metadata.get("sdpc_pacar_confidence") == 0.9
    verifier.assistant.analyze_message_impact.assert_awaited_once()
    verifier.assistant.ainvoke_multi_turn.assert_not_awaited()


async def test_task_request_with_session_uses_verify_with_context(pacar) -> None:
    processor, verifier = pacar

    result = await processor.process(_task_request(session_id="sess-123", tenant_id="tenant-a"))

    assert result.is_valid, result.errors
    assert result.metadata.get("sdpc_pacar_valid") is True
    assert result.metadata.get("sdpc_pacar_confidence") == 0.8
    verifier.assistant.ainvoke_multi_turn.assert_awaited_once()
    verifier.assistant.analyze_message_impact.assert_not_awaited()
    assert verifier.manager.added, "session history must be recorded"
    recorded = {sid for sid, _, _ in verifier.manager.added}
    assert len(recorded) == 1
    (scoped,) = recorded
    assert scoped.endswith(":sess-123") and "tenant-a" in scoped


async def test_high_risk_pacar_verdict_blocks_message(pacar) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(
        return_value={"risk_level": "high", "confidence": 0.95, "reasoning": ["risky"]}
    )

    result = await processor.process(_task_request())

    _assert_pacar_blocked(result)


async def test_pacar_deny_does_not_run_processing_strategy(pacar, monkeypatch) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(return_value={"risk_level": "high"})
    spy = AsyncMock()
    monkeypatch.setattr(processor._processing_strategy, "process", spy)

    result = await processor.process(_task_request())

    _assert_pacar_blocked(result)
    spy.assert_not_awaited()


@pytest.mark.parametrize(
    "analysis",
    [
        {"confidence": 0.9, "reasoning": ["no verdict"]},  # risk_level missing
        {"risk_level": "critical", "confidence": 0.9},
        {"risk_level": "unknown", "confidence": 0.9},
        {},
    ],
    ids=["missing", "critical", "unknown", "empty"],
)
async def test_single_turn_verdict_fails_closed(pacar, analysis: dict) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(return_value=analysis)

    result = await processor.process(_task_request())

    _assert_pacar_blocked(result)


@pytest.mark.parametrize(
    "multi_turn",
    [
        {"confidence": 0.8, "reasoning": ["no decision"]},
        {"recommended_decision": "", "confidence": 0.8},
        {"recommended_decision": None},
        {"recommended_decision": "review", "confidence": 0.8},
        {},
    ],
    ids=["missing", "empty-string", "none", "review", "empty"],
)
async def test_multi_turn_missing_decision_fails_closed(pacar, multi_turn: dict) -> None:
    processor, verifier = pacar
    verifier.assistant.ainvoke_multi_turn = AsyncMock(return_value=multi_turn)

    result = await processor.process(_task_request(session_id="sess-9", tenant_id="tenant-a"))

    _assert_pacar_blocked(result)
    assert verifier.assistant.ainvoke_multi_turn.await_count == 1


@pytest.mark.parametrize("verdict", [None, "true", 1, {}], ids=["none", "str", "int", "dict"])
async def test_non_boolean_verdict_blocks(pacar, monkeypatch, verdict) -> None:
    processor, verifier = pacar
    monkeypatch.setattr(verifier, "verify", AsyncMock(return_value={"is_valid": verdict}))

    result = await processor.process(_task_request())

    _assert_pacar_blocked(result)


@pytest.mark.parametrize("with_session", [False, True], ids=["single-turn", "multi-turn"])
async def test_pacar_exception_blocks_instead_of_raising(pacar, with_session: bool) -> None:
    processor, verifier = pacar
    boom = AsyncMock(side_effect=ConnectionError("redis down"))
    verifier.assistant.analyze_message_impact = boom
    verifier.assistant.ainvoke_multi_turn = boom
    extra = {"session_id": "sess-x", "tenant_id": "tenant-a"} if with_session else {}

    result = await processor.process(_task_request(**extra))

    _assert_pacar_blocked(result)
    assert result.metadata.get("sdpc_pacar_error") == "ConnectionError"


async def test_validation_cache_does_not_replay_prior_pacar_allow(pacar) -> None:
    processor, verifier = pacar
    msg_kwargs = {"session_id": "s1", "tenant_id": "tenant-a"}

    first = await processor.process(_task_request(**msg_kwargs))
    assert first.is_valid, first.errors

    verifier.assistant.ainvoke_multi_turn = AsyncMock(
        return_value={"recommended_decision": "reject", "confidence": 0.9}
    )
    second = await processor.process(_task_request(**msg_kwargs))

    _assert_pacar_blocked(second)
    verifier.assistant.ainvoke_multi_turn.assert_awaited_once()


async def test_cached_low_impact_allow_does_not_skip_pacar_at_high_impact(pacar) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(return_value={"risk_level": "high"})

    def query(impact: float) -> AgentMessage:
        return AgentMessage(
            content={"q": "rotate production credentials"},
            message_type=MessageType.QUERY,
            from_agent="admin-agent",
            to_agent="analysis-agent",
            impact_score=impact,
        )

    low = await processor.process(query(0.1))
    assert low.is_valid, low.errors
    assert "sdpc_pacar_valid" not in low.metadata  # PACAR not routed at low impact

    high = await processor.process(query(0.95))

    _assert_pacar_blocked(high)
    verifier.assistant.analyze_message_impact.assert_awaited_once()


async def test_session_history_is_tenant_isolated(pacar, monkeypatch) -> None:
    processor, verifier = pacar
    manager = PACARManager(config=verifier.config)
    monkeypatch.setattr(manager, "_redis", _FakeRedis())
    monkeypatch.setattr(verifier, "manager", manager)
    seen_history: list[list] = []

    async def record(content, history):
        seen_history.append(list(history))
        return {"recommended_decision": "approve", "confidence": 0.8}

    verifier.assistant.ainvoke_multi_turn = AsyncMock(side_effect=record)

    a1 = await processor.process(_task_request(session_id="shared", tenant_id="tenant-a"))
    b1 = await processor.process(_task_request(session_id="shared", tenant_id="tenant-b"))
    a2 = await processor.process(_task_request(session_id="shared", tenant_id="tenant-a"))

    assert a1.is_valid and b1.is_valid and a2.is_valid
    assert seen_history[0] == []
    assert seen_history[1] == [], "tenant-b must not see tenant-a's PACAR history"
    assert len(seen_history[2]) > 0, "tenant-a must see its own history"
    keys = sorted(manager._redis.store)
    assert len(keys) == 2, keys
    assert "tenant-a" in keys[0] and "tenant-b" in keys[1]
    stored_sessions = {json.loads(manager._redis.store[k])["session_id"] for k in keys}
    assert len(stored_sessions) == 2
