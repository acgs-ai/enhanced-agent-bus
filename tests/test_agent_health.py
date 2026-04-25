"""Smoke tests for enhanced_agent_bus.agent_health (US-001 Cat 1).

Verifies the package's public re-exports and basic model construction
so that pydantic validators and constitutional-hash invariants stay
locked against regressions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError as PydValidationError

from enhanced_agent_bus.agent_health import (
    AgentHealthRecord,
    AgentHealthStore,
    AgentHealthThresholds,
    AutonomyTier,
    HealingAction,
    HealingActionType,
    HealingOverride,
    HealingTrigger,
    HealthState,
    OverrideMode,
    emit_health_metrics,
)


def test_public_reexports_resolve() -> None:
    # Classes and enums must be importable via the package namespace.
    assert AgentHealthRecord.__name__ == "AgentHealthRecord"
    assert AgentHealthStore.__name__ == "AgentHealthStore"
    assert issubclass(HealingAction, object)
    assert set(HealthState).issuperset({HealthState(HealthState.HEALTHY.value)})
    assert set(AutonomyTier)
    assert set(HealingTrigger)
    assert set(HealingActionType)
    assert set(OverrideMode)


def test_agent_health_record_validates_fields() -> None:
    rec = AgentHealthRecord(
        agent_id="agent-1",
        health_state=HealthState.HEALTHY,
        consecutive_failure_count=0,
        memory_usage_pct=42.5,
        last_error_type=None,
        last_event_at=datetime.now(UTC),
        autonomy_tier=AutonomyTier(list(AutonomyTier)[0].value),
    )
    assert rec.agent_id == "agent-1"
    assert rec.health_state == HealthState.HEALTHY

    with pytest.raises(PydValidationError):
        AgentHealthRecord(
            agent_id="",  # empty — violates min_length
            health_state=HealthState.HEALTHY,
            consecutive_failure_count=0,
            memory_usage_pct=0.0,
            last_event_at=datetime.now(UTC),
            autonomy_tier=AutonomyTier(list(AutonomyTier)[0].value),
        )


def test_healing_action_constitutional_hash_is_locked() -> None:
    # default hash is accepted
    action = HealingAction(
        agent_id="a-1",
        trigger=HealingTrigger(list(HealingTrigger)[0].value),
        action_type=HealingActionType(list(HealingActionType)[0].value),
        tier_determined_by=AutonomyTier(list(AutonomyTier)[0].value),
        initiated_at=datetime.now(UTC),
        audit_event_id="evt-1",
    )
    assert action.constitutional_hash

    # overriding with a different hash must fail
    with pytest.raises(PydValidationError):
        HealingAction(
            agent_id="a-1",
            trigger=HealingTrigger(list(HealingTrigger)[0].value),
            action_type=HealingActionType(list(HealingActionType)[0].value),
            tier_determined_by=AutonomyTier(list(AutonomyTier)[0].value),
            initiated_at=datetime.now(UTC),
            audit_event_id="evt-1",
            constitutional_hash="0000deadbeef",
        )


def test_healing_override_expiry_must_be_after_issue() -> None:
    now = datetime.now(UTC)
    HealingOverride(
        agent_id="a-1",
        mode=OverrideMode(list(OverrideMode)[0].value),
        reason="maintenance window",
        issued_by="ops@example.com",
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    with pytest.raises(PydValidationError):
        HealingOverride(
            agent_id="a-1",
            mode=OverrideMode(list(OverrideMode)[0].value),
            reason="bad window",
            issued_by="ops@example.com",
            issued_at=now,
            expires_at=now,  # must be strictly after issued_at
        )


def test_thresholds_model_constructs() -> None:
    t = AgentHealthThresholds()
    assert t is not None


def test_emit_health_metrics_is_callable() -> None:
    # Sanity: function exists and doesn't raise on a valid record.
    rec = AgentHealthRecord(
        agent_id="agent-2",
        health_state=HealthState.HEALTHY,
        consecutive_failure_count=0,
        memory_usage_pct=12.0,
        last_event_at=datetime.now(UTC),
        autonomy_tier=AutonomyTier(list(AutonomyTier)[0].value),
    )
    emit_health_metrics(rec)
