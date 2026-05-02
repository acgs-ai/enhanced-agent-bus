"""Governance decision receipts with chained audit verification."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

from .validation_receipts import canonical_json


class GovernanceDecisionValue(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class GovernanceDecisionReceipt(BaseModel):
    """Final governance decision bound to evidence and audit chain state."""

    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    message_id: str
    message_hash: str
    decision: GovernanceDecisionValue
    reason_codes: list[str] = Field(default_factory=list)
    constitutional_hash: str
    policy_hash: str
    maci_roles_checked: list[str] = Field(default_factory=list)
    validator_receipt_ids: list[str] = Field(default_factory=list)
    autonomy_tier: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    audit_chain_hash: str


def compute_decision_chain_hash(
    receipt_data: dict[str, object],
    *,
    previous_hash: str,
) -> str:
    """Hash a receipt with its predecessor for tamper-evident chaining."""

    payload = dict(receipt_data)
    payload["audit_chain_hash"] = ""
    payload["previous_audit_chain_hash"] = previous_hash
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class GovernanceDecisionReceiptStore:
    """In-memory append-only receipt store with chain verification."""

    def __init__(self) -> None:
        self._receipts: list[GovernanceDecisionReceipt] = []
        self._lock = RLock()

    def append(
        self,
        *,
        tenant_id: str,
        message_id: str,
        message_hash: str,
        decision: GovernanceDecisionValue,
        constitutional_hash: str,
        policy_hash: str,
        reason_codes: list[str] | None = None,
        maci_roles_checked: list[str] | None = None,
        validator_receipt_ids: list[str] | None = None,
        autonomy_tier: str | None = None,
    ) -> GovernanceDecisionReceipt:
        with self._lock:
            previous_hash = self._receipts[-1].audit_chain_hash if self._receipts else ""
            data = {
                "receipt_id": str(uuid4()),
                "tenant_id": tenant_id,
                "message_id": message_id,
                "message_hash": message_hash,
                "decision": decision.value,
                "reason_codes": list(reason_codes or []),
                "constitutional_hash": constitutional_hash,
                "policy_hash": policy_hash,
                "maci_roles_checked": list(maci_roles_checked or []),
                "validator_receipt_ids": list(validator_receipt_ids or []),
                "autonomy_tier": autonomy_tier,
                "created_at": datetime.now(UTC).isoformat(),
                "audit_chain_hash": "",
            }
            receipt = GovernanceDecisionReceipt(**data)
            receipt.audit_chain_hash = compute_decision_chain_hash(
                receipt.model_dump(mode="json"),
                previous_hash=previous_hash,
            )
            self._receipts.append(receipt)
            return receipt

    def get(self, *, tenant_id: str, receipt_id: str) -> GovernanceDecisionReceipt | None:
        with self._lock:
            for receipt in self._receipts:
                if receipt.tenant_id == tenant_id and receipt.receipt_id == receipt_id:
                    return receipt
        return None

    def list_for_message(
        self,
        *,
        tenant_id: str,
        message_id: str,
    ) -> list[GovernanceDecisionReceipt]:
        with self._lock:
            return [
                receipt
                for receipt in self._receipts
                if receipt.tenant_id == tenant_id and receipt.message_id == message_id
            ]

    def verify_chain(self) -> bool:
        previous_hash = ""
        with self._lock:
            for receipt in self._receipts:
                expected = compute_decision_chain_hash(
                    receipt.model_dump(mode="json"),
                    previous_hash=previous_hash,
                )
                if not expected == receipt.audit_chain_hash:
                    return False
                previous_hash = receipt.audit_chain_hash
        return True


__all__ = [
    "GovernanceDecisionReceipt",
    "GovernanceDecisionReceiptStore",
    "GovernanceDecisionValue",
    "compute_decision_chain_hash",
]
