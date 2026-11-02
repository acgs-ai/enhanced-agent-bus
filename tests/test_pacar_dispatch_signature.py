"""
Regression: PACAR dispatch from MessageProcessor.process() must match the real
PACARVerifier signatures.

verification_orchestrator previously called ``PACARVerifier.verify(..., session_id=...)``,
which raised TypeError for every TASK_REQUEST / impact>0.8 message; the processor then
retried and rejected with max_retries_exceeded. Earlier tests hid this by replacing
``verify`` with a bare AsyncMock that accepts any kwargs. These tests keep the real
method signatures and stub only the LLM assistant and session manager underneath.

Constitutional Hash: 608508a9bd224290
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from enhanced_agent_bus.message_processor import MessageProcessor
from enhanced_agent_bus.models import AgentMessage, MessageType
from enhanced_agent_bus.sdpc.pacar_verifier import PACARVerifier


class _FakeManager:
    def __init__(self) -> None:
        self.added: list[tuple[str, object, str]] = []

    async def get_state(self, session_id: str) -> SimpleNamespace:
        return SimpleNamespace(messages=[])

    async def add_message(self, session_id, role, content, metadata=None) -> None:
        self.added.append((session_id, role, content))


def _processor_with_real_pacar() -> tuple[MessageProcessor, PACARVerifier]:
    processor = MessageProcessor(
        enable_maci=False
    )  # test-only: MACI off — testing SDPC/PACAR dispatch independently
    verifier = processor.pacar_verifier
    if not isinstance(verifier, PACARVerifier):
        pytest.skip("SDPC unavailable: processor uses no-op PACAR verifier")
    verifier.assistant = SimpleNamespace(
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
    verifier.manager = _FakeManager()
    verifier.redis_client = None
    verifier.audit_client = None
    return processor, verifier


def _task_request(**extra: object) -> AgentMessage:
    return AgentMessage(
        content={"task": "Summarize quarterly governance metrics"},
        message_type=MessageType.TASK_REQUEST,
        from_agent="admin-agent",
        to_agent="analysis-agent",
        **extra,
    )


async def test_task_request_without_session_uses_single_turn_verify() -> None:
    processor, verifier = _processor_with_real_pacar()

    result = await processor.process(_task_request())

    assert result.is_valid, result.errors
    assert result.metadata.get("sdpc_pacar_valid") is True
    assert result.metadata.get("sdpc_pacar_confidence") == 0.9
    verifier.assistant.analyze_message_impact.assert_awaited_once()
    verifier.assistant.ainvoke_multi_turn.assert_not_awaited()


async def test_task_request_with_session_uses_verify_with_context() -> None:
    processor, verifier = _processor_with_real_pacar()

    result = await processor.process(_task_request(session_id="sess-123", tenant_id="tenant-a"))

    assert result.is_valid, result.errors
    assert result.metadata.get("sdpc_pacar_valid") is True
    assert result.metadata.get("sdpc_pacar_confidence") == 0.8
    verifier.assistant.ainvoke_multi_turn.assert_awaited_once()
    verifier.assistant.analyze_message_impact.assert_not_awaited()
    assert verifier.manager.added, "session history must be recorded"
    assert {sid for sid, _, _ in verifier.manager.added} == {"sess-123"}


async def test_high_risk_pacar_verdict_is_reported_invalid() -> None:
    processor, verifier = _processor_with_real_pacar()
    verifier.assistant.analyze_message_impact = AsyncMock(
        return_value={"risk_level": "high", "confidence": 0.95, "reasoning": ["risky"]}
    )

    result = await processor.process(_task_request())

    assert result.metadata.get("sdpc_pacar_valid") is False
