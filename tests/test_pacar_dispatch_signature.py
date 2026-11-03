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
                "risk_level": "low",
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
        return {"recommended_decision": "approve", "risk_level": "low", "confidence": 0.8}

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


@pytest.mark.parametrize("extra", [{}, {"session_id": "sess-default", "tenant_id": "tenant-a"}])
async def test_default_placeholder_reviewer_denies(monkeypatch, extra) -> None:
    """With no real reviewer wired, the built-in placeholder must block PACAR traffic."""
    from enhanced_agent_bus.sdpc.pacar_verifier import _DefaultAssistant

    processor = MessageProcessor(enable_maci=False)  # test-only: MACI off
    verifier = processor.pacar_verifier
    if not isinstance(verifier, PACARVerifier):
        pytest.fail("SDPC unavailable: processor uses no-op PACAR verifier")
    monkeypatch.setattr(verifier, "assistant", _DefaultAssistant())
    monkeypatch.setattr(verifier, "manager", _FakeManager())
    monkeypatch.setattr(verifier, "redis_client", None)
    monkeypatch.setattr(verifier, "audit_client", None)

    result = await processor.process(_task_request(**extra))

    _assert_pacar_blocked(result)


@pytest.mark.parametrize("decision", ["reject", "review", "escalate", ""])
async def test_single_turn_low_risk_with_non_approve_decision_blocks(pacar, decision) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(
        return_value={"risk_level": "low", "confidence": 0.9, "recommended_decision": decision}
    )

    result = await processor.process(_task_request())

    _assert_pacar_blocked(result)


async def test_single_turn_low_risk_with_approve_decision_allows(pacar) -> None:
    processor, verifier = pacar
    verifier.assistant.analyze_message_impact = AsyncMock(
        return_value={"risk_level": "low", "confidence": 0.9, "recommended_decision": "approve"}
    )

    result = await processor.process(_task_request())

    assert result.is_valid, result.errors
    assert result.metadata.get("sdpc_pacar_valid") is True


async def test_routed_message_with_missing_pacar_verdict_blocks(pacar, monkeypatch) -> None:
    """Defense in depth: if SDPC drops the PACAR verdict, the coordinator still denies."""
    processor, _ = pacar
    monkeypatch.setattr(
        processor._verification_orchestrator,
        "_perform_sdpc",
        AsyncMock(return_value=({}, {})),
    )

    result = await processor.process(_task_request())

    assert result.is_valid is False
    assert result.decision == "DENY"
    assert result.metadata.get("rejection_reason") == "pacar_verification_failed"
    assert "sdpc_pacar_valid" not in result.metadata


async def test_unrouted_message_with_missing_pacar_verdict_still_processes(pacar, monkeypatch):
    processor, _ = pacar
    monkeypatch.setattr(
        processor._verification_orchestrator,
        "_perform_sdpc",
        AsyncMock(return_value=({}, {})),
    )
    strategy_spy = AsyncMock(wraps=processor._verification_coordinator._processing_strategy.process)
    monkeypatch.setattr(
        processor._verification_coordinator._processing_strategy, "process", strategy_spy
    )
    msg = AgentMessage(
        content={"q": "status"},
        message_type=MessageType.QUERY,
        from_agent="admin-agent",
        to_agent="analysis-agent",
    )

    result = await processor.process(msg)

    assert result.is_valid, result.errors
    assert result.metadata.get("rejection_reason") != "pacar_verification_failed"
    strategy_spy.assert_awaited_once()


@pytest.mark.parametrize("risk", [None, "high", "critical", "unreviewed"])
async def test_multi_turn_approve_with_unacceptable_risk_blocks(pacar, risk) -> None:
    processor, verifier = pacar
    payload = {"recommended_decision": "approve", "confidence": 0.9, "reasoning": ["x"]}
    if risk is not None:
        payload["risk_level"] = risk
    verifier.assistant.ainvoke_multi_turn = AsyncMock(return_value=payload)

    result = await processor.process(_task_request(session_id="sess-risk", tenant_id="tenant-a"))

    _assert_pacar_blocked(result)


@pytest.mark.parametrize(
    ("reviewer", "risk", "enforced"),
    [
        ("approve", "high", "reject"),
        ("approve", None, "reject"),
        ("review", "low", "review"),
        ("approve", "low", "approve"),
    ],
)
async def test_recorded_decision_matches_enforced_outcome(pacar, reviewer, risk, enforced) -> None:
    from enhanced_agent_bus.sdpc.conversation import MessageRole

    processor, verifier = pacar
    payload = {"recommended_decision": reviewer, "confidence": 0.9, "reasoning": ["x"]}
    if risk is not None:
        payload["risk_level"] = risk
    verifier.assistant.ainvoke_multi_turn = AsyncMock(return_value=payload)
    audit = SimpleNamespace(report_decision=AsyncMock())
    verifier.audit_client = audit

    result = await processor.process(_task_request(session_id="sess-rec", tenant_id="tenant-a"))

    if enforced == "approve":
        assert result.is_valid is True
    else:
        _assert_pacar_blocked(result)
    system_entries = [c for _, role, c in verifier.manager.added if role == MessageRole.SYSTEM]
    assert system_entries == [enforced]
    audit.report_decision.assert_awaited_once()
    reported = audit.report_decision.await_args.args[0]
    assert reported["recommended_decision"] == enforced
    assert reported["reviewer_decision"] == reviewer


async def test_session_history_is_capped_per_session() -> None:
    from enhanced_agent_bus.sdpc.conversation import MessageRole
    from enhanced_agent_bus.sdpc.pacar_manager import _MAX_SESSION_MESSAGES

    manager = PACARManager()
    manager._redis = _FakeRedis()
    for i in range(_MAX_SESSION_MESSAGES + 60):
        await manager.add_message("t:sess", MessageRole.USER, f"m{i}")

    state = await manager.get_state("t:sess")
    assert len(state.messages) == _MAX_SESSION_MESSAGES
    assert state.messages[-1].content == f"m{_MAX_SESSION_MESSAGES + 59}"
    persisted = json.loads(manager._redis.store["pacar:session:t:sess"])
    assert len(persisted["messages"]) == _MAX_SESSION_MESSAGES


@pytest.mark.parametrize("risk", [None, "unreviewed", "high", "critical", "unknown"])
async def test_asc_verifier_fails_closed_on_non_acceptable_risk(risk) -> None:
    from enhanced_agent_bus.deliberation_layer.intent_classifier import IntentType
    from enhanced_agent_bus.sdpc.asc_verifier import ASCVerifier

    verifier = ASCVerifier()
    if risk != "unreviewed":
        payload = {} if risk is None else {"risk_level": risk}
        verifier.assistant = SimpleNamespace(analyze_message_impact=AsyncMock(return_value=payload))

    result = await verifier.verify("The meeting is on 3 May in Paris.", IntentType.FACTUAL)

    assert result["is_valid"] is False


async def test_asc_verifier_accepts_low_risk() -> None:
    from enhanced_agent_bus.deliberation_layer.intent_classifier import IntentType
    from enhanced_agent_bus.sdpc.asc_verifier import ASCVerifier

    verifier = ASCVerifier()
    verifier.assistant = SimpleNamespace(
        analyze_message_impact=AsyncMock(return_value={"risk_level": "low", "confidence": 0.9})
    )

    result = await verifier.verify("The meeting is on 3 May in Paris.", IntentType.FACTUAL)

    assert result["is_valid"] is True
