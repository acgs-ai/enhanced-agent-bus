"""Critical-path tests for governance decision receipts."""

from __future__ import annotations

from enhanced_agent_bus.governance.decision_receipts import (
    GovernanceDecisionReceiptStore,
    GovernanceDecisionValue,
)


def test_decision_receipt_created_for_approval() -> None:
    store = GovernanceDecisionReceiptStore()

    receipt = store.append(
        tenant_id="tenant-a",
        message_id="msg-1",
        message_hash="hash-1",
        decision=GovernanceDecisionValue.APPROVED,
        reason_codes=[],
        constitutional_hash="constitution-v1",
        policy_hash="policy-v1",
        maci_roles_checked=["proposer", "validator"],
        validator_receipt_ids=["vr-1"],
        autonomy_tier="bounded",
    )

    assert receipt.tenant_id == "tenant-a"
    assert receipt.message_hash == "hash-1"
    assert receipt.policy_hash == "policy-v1"
    assert receipt.audit_chain_hash
    assert store.verify_chain() is True


def test_decision_receipt_created_for_rejection() -> None:
    store = GovernanceDecisionReceiptStore()

    receipt = store.append(
        tenant_id="tenant-a",
        message_id="msg-2",
        message_hash="hash-2",
        decision=GovernanceDecisionValue.REJECTED,
        reason_codes=["policy.denied"],
        constitutional_hash="constitution-v1",
        policy_hash="policy-v1",
    )

    assert receipt.decision == GovernanceDecisionValue.REJECTED
    assert receipt.reason_codes == ["policy.denied"]


def test_audit_chain_detects_tampering() -> None:
    store = GovernanceDecisionReceiptStore()
    receipt = store.append(
        tenant_id="tenant-a",
        message_id="msg-1",
        message_hash="hash-1",
        decision=GovernanceDecisionValue.APPROVED,
        constitutional_hash="constitution-v1",
        policy_hash="policy-v1",
    )

    receipt.reason_codes.append("tampered")

    assert store.verify_chain() is False


def test_tenant_cannot_query_other_tenant_receipt() -> None:
    store = GovernanceDecisionReceiptStore()
    receipt = store.append(
        tenant_id="tenant-a",
        message_id="msg-1",
        message_hash="hash-1",
        decision=GovernanceDecisionValue.APPROVED,
        constitutional_hash="constitution-v1",
        policy_hash="policy-v1",
    )

    assert store.get(tenant_id="tenant-b", receipt_id=receipt.receipt_id) is None
