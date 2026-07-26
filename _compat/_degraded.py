"""Registry of `_compat` shims currently serving a degraded fallback.

The extraction gap is invisible at the seam: every ``_compat`` module imports
successfully whether it re-exports the real ``src.core.*`` implementation or a
standalone fallback. Callers that guard with ``except ImportError`` therefore
never learn the difference, and a permissive fallback reads as a working
dependency.

This registry makes the substitution observable. A fallback branch registers
itself when selected; the runtime profile refuses to start in production while a
``security`` or ``governance`` tier entry is active, and ``GET /health`` reports
the active set so an operator does not have to read logs to know the process is
degraded.

Deliberately stdlib-only and side-effect-free at import: it is imported from
inside ``_compat`` fallback branches, so any dependency of its own could
reintroduce the cycle it exists to report on.
"""

from __future__ import annotations

import threading
from typing import Literal

#: ``security``     — authn/authz, crypto, tenant isolation.
#: ``governance``   — policy, MACI, audit, constitutional identity.
#: ``observability``— metrics, tracing, structured logging.
Tier = Literal["security", "governance", "observability"]

#: Tiers that must block a production start. Observability degradation is
#: reportable but not fatal; a governance runtime that cannot authorise or
#: cannot record its decisions is not a governance runtime.
BLOCKING_TIERS: frozenset[str] = frozenset({"security", "governance"})

_lock = threading.Lock()
_registry: dict[str, str] = {}


def register(name: str, tier: Tier) -> None:
    """Record that *name* is serving its degraded fallback.

    Idempotent: shim modules are cached in ``sys.modules``, so the fallback
    branch runs at most once per interpreter anyway.
    """

    with _lock:
        _registry[name] = tier


def unregister(name: str) -> None:
    """Drop *name* from the registry if present."""

    with _lock:
        _registry.pop(name, None)


def clear() -> None:
    """Empty the registry. Intended for tests that install a real dependency."""

    with _lock:
        _registry.clear()


def active() -> dict[str, str]:
    """Return a snapshot of ``{name: tier}`` for every active degradation."""

    with _lock:
        return dict(_registry)


def active_blocking() -> dict[str, str]:
    """Return only the degradations that must block a production start."""

    return {name: tier for name, tier in active().items() if tier in BLOCKING_TIERS}


def describe(entries: dict[str, str] | None = None) -> str:
    """Render *entries* (default: all active) as a stable, sorted summary."""

    items = active() if entries is None else entries
    return ", ".join(f"{name} ({tier})" for name, tier in sorted(items.items()))


__all__ = [
    "BLOCKING_TIERS",
    "Tier",
    "active",
    "active_blocking",
    "clear",
    "describe",
    "register",
    "unregister",
]
