"""Per-agent governance scope — DI scoping for agent execution contexts.

Each agent session gets an isolated AgentScope that carries its own
GovernanceService, PolicyStorage, and AuditLog. Services registered here
do not leak to other concurrent sessions.

Constitutional Hash: 608508a9bd224290

Pattern: AFFiNE Scope/Service/Store hierarchy (simplified Python port).
ADR: docs/wiki/architecture/adr/019-di-scoping-agent-contexts.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.shared.di_container import AgentScope as _AgentScope
from src.core.shared.di_container import DIContainer


@dataclass
class GovernedAgentScope:
    """Governance-aware scope for a single agent execution session.

    Wire governance services into an isolated child scope so that concurrent
    agent sessions cannot accidentally share policy state or audit trails.

    Usage::

        with GovernedAgentScope(agent_id="session-42") as scope:
            policy = scope.policy_storage
            # ... govern the agent call ...

    Constitutional Hash: 608508a9bd224290
    """

    agent_id: str
    _scope: _AgentScope = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id must be a non-empty string")
        self._scope = DIContainer.child_scope(scope_id=self.agent_id)

    # ------------------------------------------------------------------
    # Scoped service accessors
    # ------------------------------------------------------------------

    def register(self, service_type: type, instance: object) -> None:
        """Register a scoped service (does not affect the parent container)."""
        self._scope.register(service_type, instance)

    def get(self, service_type: type) -> object:
        """Resolve a service from this scope, falling through to parent."""
        return self._scope.get(service_type)

    def register_named(self, name: str, instance: object) -> None:
        """Register a named scoped service."""
        self._scope.register_named(name, instance)

    def get_named(self, name: str) -> object:
        """Resolve a named service from this scope, falling through to parent."""
        return self._scope.get_named(name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release all scoped service overrides."""
        self._scope.reset()

    def __enter__(self) -> "GovernedAgentScope":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.cleanup()


__all__ = ["GovernedAgentScope"]
