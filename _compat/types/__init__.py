"""Shim package for src.core.shared.types.

This package marker enables ``from enhanced_agent_bus._compat.types.protocol_types import X``
patterns. It re-exports all names from the flat ``_compat/types.py`` module via a relative
import so that ``from enhanced_agent_bus._compat.types import CONSTITUTIONAL_HASH`` also works
when the package form is resolved.

NOTE: Python resolves ``_compat.types`` as this directory package (not the sibling
``_compat/types.py`` flat module) once the directory exists, so we must replicate the
flat module exports here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

_use_fallback = False
if not TYPE_CHECKING:
    try:
        from src.core.shared.types import *  # noqa: F403
    except ImportError:
        _use_fallback = True

# The same concrete definitions serve standalone runtime and static consumers.
if TYPE_CHECKING or _use_fallback:
    # Standalone type alias fallbacks — mirrors _compat/types.py
    JSONPrimitive: TypeAlias = str | int | float | bool | None
    JSONDict: TypeAlias = dict[str, Any]
    JSONList: TypeAlias = list[Any]
    JSONValue: TypeAlias = JSONPrimitive | JSONDict | JSONList
    JSONType: TypeAlias = JSONDict | JSONList
    MetadataDict: TypeAlias = dict[str, Any]
    NestedDict: TypeAlias = dict[str, Any]
    RecursiveDict: TypeAlias = dict[str, Any]

    AgentID: TypeAlias = str
    AgentInfo: TypeAlias = dict[str, Any]
    AgentIdentity: TypeAlias = str
    AgentMetadata: TypeAlias = dict[str, Any]
    AgentState: TypeAlias = dict[str, Any]
    AgentContext: TypeAlias = dict[str, Any]
    ContextData: TypeAlias = dict[str, Any]

    MessageID: TypeAlias = str
    MessagePayload: TypeAlias = dict[str, Any]
    MessageHeaders: TypeAlias = dict[str, str]
    MessageMetadata: TypeAlias = dict[str, Any]
    KafkaMessage: TypeAlias = dict[str, Any]

    EventID: TypeAlias = str
    EventData: TypeAlias = dict[str, Any]
    EventContext: TypeAlias = dict[str, Any]

    WorkflowID: TypeAlias = str
    WorkflowState: TypeAlias = dict[str, Any]
    WorkflowContext: TypeAlias = dict[str, Any]
    SessionData: TypeAlias = dict[str, Any]
    StepParameters: TypeAlias = dict[str, Any]
    StepResult: TypeAlias = dict[str, Any]
    TopicName: TypeAlias = str
    MemoryData: TypeAlias = dict[str, Any]

    CorrelationID: TypeAlias = str
    TenantID: TypeAlias = str
    Timestamp: TypeAlias = str
    TraceID: TypeAlias = str
    ErrorCode: TypeAlias = str
    ErrorContext: TypeAlias = dict[str, Any]
    ErrorDetails: TypeAlias = dict[str, Any]
    PolicyID: TypeAlias = str
    PolicyContext: TypeAlias = dict[str, Any]
    PolicyData: TypeAlias = dict[str, Any]
    PolicyDecision: TypeAlias = dict[str, Any]
    DecisionData: TypeAlias = dict[str, Any]
    SecurityContext: TypeAlias = dict[str, Any]
    ValidationContext: TypeAlias = dict[str, Any]
    ValidationErrors: TypeAlias = list[dict[str, Any]]
    PermissionSet: TypeAlias = set[str]
    ModelID: TypeAlias = str
    ModelMetadata: TypeAlias = dict[str, Any]
    ModelParameters: TypeAlias = dict[str, Any]
    PerformanceMetrics: TypeAlias = dict[str, int | float | str | None]
    TelemetryData: TypeAlias = dict[str, Any]
    AuditEntry: TypeAlias = dict[str, Any]
    AuditTrail: TypeAlias = list[dict[str, Any]]
    AuthContext: TypeAlias = dict[str, Any]
    AuthCredentials: TypeAlias = dict[str, Any]
    AuthToken: TypeAlias = str
    CacheKey: TypeAlias = str
    CacheTTL: TypeAlias = int
    CacheValue: TypeAlias = Any
    ConfigDict: TypeAlias = dict[str, Any]
    ConfigValue: TypeAlias = Any
    ConstitutionalContext: TypeAlias = dict[str, Any]
    RedisValue: TypeAlias = str | bytes
    EventMetadata: TypeAlias = dict[str, Any]

    CONSTITUTIONAL_HASH = "608508a9bd224290"
