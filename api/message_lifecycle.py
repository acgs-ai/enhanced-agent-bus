"""Tenant-bound message lifecycle state tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Any

from pydantic import BaseModel, Field


class MessageLifecycleState(StrEnum):
    """Explicit lifecycle states for submitted messages."""

    RECEIVED = "received"
    ACCEPTED_FOR_PROCESSING = "accepted_for_processing"
    GOVERNANCE_PENDING = "governance_pending"
    GOVERNANCE_APPROVED = "governance_approved"
    GOVERNANCE_REJECTED = "governance_rejected"
    ROUTED = "routed"
    EXECUTION_PENDING = "execution_pending"
    EXECUTED = "executed"
    FAILED = "failed"


class MessageStatusRecord(BaseModel):
    """Persistable status record keyed by tenant and message id."""

    tenant_id: str
    message_id: str
    state: MessageLifecycleState
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class InMemoryMessageStatusStore:
    """Development/demo status store with tenant-bound lookups."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], MessageStatusRecord] = {}
        self._lock = RLock()

    def record(
        self,
        *,
        tenant_id: str,
        message_id: str,
        state: MessageLifecycleState | str,
        details: dict[str, Any] | None = None,
    ) -> MessageStatusRecord:
        record = MessageStatusRecord(
            tenant_id=tenant_id,
            message_id=message_id,
            state=MessageLifecycleState(state),
            details=dict(details or {}),
        )
        with self._lock:
            self._records[(tenant_id, message_id)] = record
        return record

    def get(self, *, tenant_id: str, message_id: str) -> MessageStatusRecord | None:
        with self._lock:
            return self._records.get((tenant_id, message_id))


__all__ = [
    "InMemoryMessageStatusStore",
    "MessageLifecycleState",
    "MessageStatusRecord",
]
