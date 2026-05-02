"""Critical-path tests for independent validation receipts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from enhanced_agent_bus.governance.validation_receipts import (
    IndependentValidationReceipt,
    ValidationReceiptError,
    ValidationReceiptVerifier,
    compute_message_hash,
    sign_validation_receipt,
)
from enhanced_agent_bus.models import AgentMessage, MessageType, Priority


def _message() -> AgentMessage:
    return AgentMessage(
        message_id="msg-1",
        content={"text": "approve deployment"},
        from_agent="agent-origin",
        to_agent="agent-exec",
        tenant_id="tenant-a",
        message_type=MessageType.GOVERNANCE_REQUEST,
        priority=Priority.HIGH,
    )


def _receipt(message: AgentMessage, **overrides: object) -> IndependentValidationReceipt:
    now = datetime.now(UTC)
    data = {
        "tenant_id": "tenant-a",
        "message_id": message.message_id,
        "message_hash": compute_message_hash(message),
        "originating_agent_id": "agent-origin",
        "validator_agent_id": "agent-validator",
        "validator_role": "validator",
        "validation_stage": "independent",
        "decision": "approve",
        "policy_hash": "policy-v1",
        "constitutional_hash": message.constitutional_hash,
        "issued_at": now,
        "expires_at": now + timedelta(minutes=5),
        "signature": "",
    }
    data.update(overrides)
    return IndependentValidationReceipt(**data)


def test_unsigned_receipt_rejected_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("EAB_RECEIPT_SIGNING_SECRET", "secret")
    message = _message()
    verifier = ValidationReceiptVerifier(signing_secret="secret")

    with pytest.raises(ValidationReceiptError, match="unsigned"):
        verifier.verify(
            _receipt(message),
            tenant_id="tenant-a",
            message=message,
            policy_hash="policy-v1",
            constitutional_hash=message.constitutional_hash,
            validator_roles={"validator"},
        )


def test_expired_receipt_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    message = _message()
    verifier = ValidationReceiptVerifier()
    expired = _receipt(message, expires_at=datetime.now(UTC) - timedelta(seconds=1))

    with pytest.raises(ValidationReceiptError, match="expired"):
        verifier.verify(
            expired,
            tenant_id="tenant-a",
            message=message,
            policy_hash="policy-v1",
            constitutional_hash=message.constitutional_hash,
            validator_roles={"validator"},
        )


def test_replayed_receipt_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("EAB_RECEIPT_SIGNING_SECRET", "secret")
    message = _message()
    receipt = _receipt(message)
    receipt.signature = sign_validation_receipt(receipt, secret="secret")
    verifier = ValidationReceiptVerifier(signing_secret="secret")

    verifier.verify(
        receipt,
        tenant_id="tenant-a",
        message=message,
        policy_hash="policy-v1",
        constitutional_hash=message.constitutional_hash,
        validator_roles={"validator"},
    )
    with pytest.raises(ValidationReceiptError, match="replay"):
        verifier.verify(
            receipt,
            tenant_id="tenant-a",
            message=message,
            policy_hash="policy-v1",
            constitutional_hash=message.constitutional_hash,
            validator_roles={"validator"},
        )


def test_validator_same_as_originator_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    message = _message()
    verifier = ValidationReceiptVerifier()

    with pytest.raises(ValidationReceiptError, match="cannot validate"):
        verifier.verify(
            _receipt(message, validator_agent_id="agent-origin"),
            tenant_id="tenant-a",
            message=message,
            policy_hash="policy-v1",
            constitutional_hash=message.constitutional_hash,
            validator_roles={"validator"},
        )


def test_valid_signed_receipt_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "prod")
    monkeypatch.setenv("EAB_RECEIPT_SIGNING_SECRET", "secret")
    message = _message()
    receipt = _receipt(message)
    receipt.signature = sign_validation_receipt(receipt, secret="secret")
    verifier = ValidationReceiptVerifier(signing_secret="secret")

    verified = verifier.verify(
        receipt,
        tenant_id="tenant-a",
        message=message,
        policy_hash="policy-v1",
        constitutional_hash=message.constitutional_hash,
        validator_roles={"validator"},
    )

    assert verified.receipt_id == receipt.receipt_id


def test_tenant_cannot_reuse_other_tenant_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EAB_PROFILE", "dev")
    message = _message()
    verifier = ValidationReceiptVerifier()

    with pytest.raises(ValidationReceiptError, match="tenant"):
        verifier.verify(
            _receipt(message, tenant_id="tenant-b"),
            tenant_id="tenant-a",
            message=message,
            policy_hash="policy-v1",
            constitutional_hash=message.constitutional_hash,
            validator_roles={"validator"},
        )
