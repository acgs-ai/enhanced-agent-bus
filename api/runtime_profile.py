"""Runtime profile controls for fail-closed governance behavior."""

from __future__ import annotations

import os
from enum import StrEnum


class RuntimeProfile(StrEnum):
    """Explicit runtime profiles supported by Enhanced Agent Bus."""

    DEV = "dev"
    DEMO = "demo"
    PROD = "prod"


_PROFILE_ALIASES = {
    "development": RuntimeProfile.DEV,
    "dev": RuntimeProfile.DEV,
    "test": RuntimeProfile.DEV,
    "testing": RuntimeProfile.DEV,
    "ci": RuntimeProfile.DEV,
    "demo": RuntimeProfile.DEMO,
    "production": RuntimeProfile.PROD,
    "prod": RuntimeProfile.PROD,
}

_DEV_FALLBACKS = frozenset(
    {
        "agent_bus_mock",
        "governance_state",
        "message_status_store",
        "policy_backend_mock",
        "validator_receipt_unsigned",
        "workflow_repository",
    }
)
_DEMO_FALLBACKS = frozenset(
    {
        "agent_bus_mock",
        "message_status_store",
        "policy_backend_mock",
        "workflow_repository",
    }
)


def current_profile() -> RuntimeProfile:
    """Return the active runtime profile.

    ``EAB_PROFILE`` is authoritative. ``ENVIRONMENT`` is only a compatibility
    bridge for older deployments and tests.
    """

    raw_profile = os.environ.get("EAB_PROFILE")
    if raw_profile:
        normalized = raw_profile.strip().lower()
        if normalized in _PROFILE_ALIASES:
            return _PROFILE_ALIASES[normalized]
        raise RuntimeError(
            "Invalid EAB_PROFILE. Expected one of: dev, demo, prod."
        )

    environment = os.environ.get("ENVIRONMENT", "prod").strip().lower()
    return _PROFILE_ALIASES.get(environment, RuntimeProfile.PROD)


def is_dev() -> bool:
    """Return True for the development profile."""

    return current_profile() is RuntimeProfile.DEV


def is_demo() -> bool:
    """Return True for the demo profile."""

    return current_profile() is RuntimeProfile.DEMO


def is_prod() -> bool:
    """Return True for the production profile."""

    return current_profile() is RuntimeProfile.PROD


def allow_fallback(feature_name: str) -> bool:
    """Return whether a non-durable/mock fallback is allowed for this feature."""

    if is_dev():
        return feature_name in _DEV_FALLBACKS
    if is_demo():
        return feature_name in _DEMO_FALLBACKS
    return False


def require_prod_dependency(name: str, condition: object) -> None:
    """Raise in production when a required dependency condition is not satisfied."""

    if is_prod() and not bool(condition):
        raise RuntimeError(f"Production dependency unavailable: {name}")


def require_auth_secret() -> None:
    """Require at least one supported auth secret marker in production."""

    configured = any(
        os.environ.get(name)
        for name in (
            "ACGS2_SERVICE_SECRET",
            "JWT_SECRET",
            "JWT_SECRET_KEY",
            "EAB_AUTH_SECRET",
        )
    )
    require_prod_dependency("auth_secret", configured)


__all__ = [
    "RuntimeProfile",
    "allow_fallback",
    "current_profile",
    "is_demo",
    "is_dev",
    "is_prod",
    "require_auth_secret",
    "require_prod_dependency",
]
