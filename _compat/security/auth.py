"""Shim for src.core.shared.security.auth."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, status

from enhanced_agent_bus.api.runtime_profile import is_prod

__all__ = [
    "UserClaims",
    "get_current_user",
    "require_auth",
    "verify_token",
]

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials
    from src.core.shared.security.auth import UserClaims, get_current_user, verify_token
else:
    try:
        from src.core.shared.security import auth as _shared_auth
    except ImportError:
        _shared_auth = None

    if _shared_auth is not None:
        UserClaims = _shared_auth.UserClaims
        get_current_user = _shared_auth.get_current_user
        verify_token = _shared_auth.verify_token
        require_auth = getattr(_shared_auth, "require_auth", _shared_auth.get_current_user)
    else:

        @dataclass
        class UserClaims:
            sub: str = "anonymous"
            tenant_id: str = "default"
            roles: list[str] = field(default_factory=list)
            permissions: list[str] = field(default_factory=list)
            exp: int = 0
            iat: int = 0
            iss: str = "acgs2"
            aud: str = "acgs2-api"
            jti: str = ""
            constitutional_hash: str = ""
            email: str = ""
            metadata: dict[str, Any] = field(default_factory=dict)

        async def get_current_user(
            credentials: HTTPAuthorizationCredentials | None = None,
        ) -> UserClaims:
            if is_prod():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication dependency unavailable in production",
                )
            del credentials
            return UserClaims()

        async def require_auth(
            credentials: HTTPAuthorizationCredentials | None = None,
        ) -> UserClaims:
            if is_prod():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication dependency unavailable in production",
                )
            del credentials
            return UserClaims()

        def verify_token(token: str) -> UserClaims:
            if is_prod():
                raise RuntimeError("Authentication dependency unavailable in production")
            del token
            return UserClaims()
