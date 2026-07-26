"""Shim for src.core.shared.security.rbac.

The standalone fallback below is **fail-closed**. It previously returned ``True``
from every check, which combined with the shim's own import always succeeding to
make the ``except ImportError`` guard in
``enhanced_agent_bus.api.routes.agent_health.require_operator_role`` unreachable:
a request carrying no ``Authorization`` header received a valid operator identity
under any profile. Denying is the only safe answer from a component that cannot
authorise anything.

``validate_operator_token`` raises rather than returning a sentinel, because its
contract is to *return an identity* — there is no fail-closed value it could
return. It raises ``RBACUnavailableError``, which subclasses ``ImportError`` so
that callers already guarding the seam with ``except ImportError`` take their
strict path without modification.
"""

from __future__ import annotations

import logging
from typing import Any

from .._degraded import register as _register_degraded

logger = logging.getLogger(__name__)

_UNAVAILABLE = (
    "RBAC is unavailable in the standalone distribution: "
    "src.core.shared.security.rbac is not installed"
)


class RBACUnavailableError(ImportError):
    """Raised when an RBAC decision is requested but no RBAC backend exists.

    Subclasses ``ImportError`` so existing ``except ImportError`` seams treat an
    unavailable backend the same way they treat an unimportable one.
    """


try:
    from src.core.shared.security.rbac import *  # noqa: F403
except ImportError:
    _register_degraded("security.rbac", "security")
    logger.warning(
        "RBAC backend unavailable; all permission checks will be denied. %s",
        _UNAVAILABLE,
    )

    async def validate_operator_token(token: str = "", **kwargs: Any) -> str:
        """Fail closed: refuse to mint an operator identity without a backend."""

        raise RBACUnavailableError(_UNAVAILABLE)

    async def check_permission(
        user_id: str = "",
        permission: str = "",
        resource: str = "",
        **kwargs: Any,
    ) -> bool:
        """Fail closed: deny every permission check."""

        logger.warning(
            "Denying permission check without an RBAC backend "
            "(user_id=%s, permission=%s, resource=%s)",
            user_id,
            permission,
            resource,
        )
        return False

    class RBACEnforcer:
        """Fail-closed RBAC enforcer used when no backend is available."""

        def __init__(self, **kwargs: Any) -> None:
            pass

        async def enforce(self, subject: str, action: str, resource: str) -> bool:
            """Fail closed: refuse every action."""

            logger.warning(
                "Denying action without an RBAC backend "
                "(subject=%s, action=%s, resource=%s)",
                subject,
                action,
                resource,
            )
            return False

        async def has_role(self, subject: str, role: str) -> bool:
            """Fail closed: grant no roles."""

            logger.warning(
                "Denying role check without an RBAC backend (subject=%s, role=%s)",
                subject,
                role,
            )
            return False
