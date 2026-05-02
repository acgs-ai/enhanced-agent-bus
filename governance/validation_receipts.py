"""Verifiable independent validation receipt primitives."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from enhanced_agent_bus.api.runtime_profile import is_prod


class ValidationReceiptError(ValueError):
    """Raised when an independent validation receipt is not acceptable."""


class ValidatorDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class IndependentValidationReceipt(BaseModel):
    """Evidence that a distinct validator reviewed a specific message."""

    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    message_id: str
    message_hash: str
    originating_agent_id: str
    validator_agent_id: str
    validator_role: str
    validation_stage: Literal["independent"]
    decision: Literal["approve", "reject"]
    policy_hash: str
    constitutional_hash: str
    issued_at: datetime
    expires_at: datetime
    signature: str = ""


def canonical_json(value: Any) -> str:
    """Serialize governance evidence into stable JSON."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_message_hash(message: Any) -> str:
    """Compute a stable SHA-256 hash for an AgentMessage-like object."""

    if hasattr(message, "to_dict"):
        payload = message.to_dict()
    elif isinstance(message, BaseModel):
        payload = message.model_dump(mode="json")
    elif isinstance(message, dict):
        payload = dict(message)
    else:
        payload = {
            "content": getattr(message, "content", None),
            "from_agent": getattr(message, "from_agent", None),
            "message_id": getattr(message, "message_id", None),
            "message_type": str(getattr(message, "message_type", "")),
            "tenant_id": getattr(message, "tenant_id", None),
            "to_agent": getattr(message, "to_agent", None),
        }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _signature_payload(receipt: IndependentValidationReceipt) -> str:
    data = receipt.model_dump(mode="json")
    data["signature"] = ""
    return canonical_json(data)


def sign_validation_receipt(
    receipt: IndependentValidationReceipt,
    *,
    secret: str | None = None,
) -> str:
    """Return the HMAC signature for a receipt."""

    signing_secret = secret or os.environ.get("EAB_RECEIPT_SIGNING_SECRET", "")
    if not signing_secret:
        raise ValidationReceiptError("receipt signing secret is required")
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        _signature_payload(receipt).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:{digest}"


class ValidationReceiptVerifier:
    """Server-side verifier with replay protection."""

    def __init__(self, *, signing_secret: str | None = None) -> None:
        self._signing_secret = signing_secret
        self._used_receipts: set[str] = set()
        self._lock = RLock()

    def verify(
        self,
        receipt: IndependentValidationReceipt,
        *,
        tenant_id: str,
        message: Any,
        policy_hash: str,
        constitutional_hash: str,
        validator_roles: set[str],
        now: datetime | None = None,
    ) -> IndependentValidationReceipt:
        timestamp = now or datetime.now(UTC)
        message_hash = compute_message_hash(message)

        if receipt.tenant_id != tenant_id:
            raise ValidationReceiptError("receipt tenant does not match authenticated tenant")
        if receipt.message_id != getattr(message, "message_id", None):
            raise ValidationReceiptError("receipt message_id does not match message")
        if receipt.message_hash != message_hash:
            raise ValidationReceiptError("receipt message_hash does not match message")
        if receipt.originating_agent_id == receipt.validator_agent_id:
            raise ValidationReceiptError("originating agent cannot validate its own message")
        if receipt.validator_role not in validator_roles:
            raise ValidationReceiptError("validator role is not authorized")
        if receipt.expires_at <= timestamp:
            raise ValidationReceiptError("receipt is expired")
        if receipt.policy_hash != policy_hash:
            raise ValidationReceiptError("receipt policy hash mismatch")
        if receipt.constitutional_hash != constitutional_hash:
            raise ValidationReceiptError("receipt constitutional hash mismatch")
        if is_prod() and not receipt.signature:
            raise ValidationReceiptError("unsigned validation receipts are rejected in prod")

        if receipt.signature:
            expected = sign_validation_receipt(
                receipt,
                secret=self._signing_secret,
            )
            if not hmac.compare_digest(receipt.signature, expected):
                raise ValidationReceiptError("receipt signature mismatch")

        with self._lock:
            if receipt.receipt_id in self._used_receipts:
                raise ValidationReceiptError("receipt replay detected")
            self._used_receipts.add(receipt.receipt_id)

        return receipt


class InMemoryValidationReceiptStore:
    """Server-side receipt persistence for tests and controlled dev/demo flows."""

    def __init__(self) -> None:
        self._receipts: dict[str, IndependentValidationReceipt] = {}
        self._lock = RLock()

    def put(self, receipt: IndependentValidationReceipt) -> None:
        with self._lock:
            self._receipts[receipt.receipt_id] = receipt

    def get(self, receipt_id: str) -> IndependentValidationReceipt | None:
        with self._lock:
            return self._receipts.get(receipt_id)


__all__ = [
    "InMemoryValidationReceiptStore",
    "IndependentValidationReceipt",
    "ValidationReceiptError",
    "ValidationReceiptVerifier",
    "compute_message_hash",
    "sign_validation_receipt",
]
