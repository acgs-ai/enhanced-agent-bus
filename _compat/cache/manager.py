"""Shim for src.core.shared.cache.manager."""

from __future__ import annotations

from typing import Any, Protocol, cast


class _CacheManagerProtocol(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def clear(self) -> None: ...
    async def has(self, key: str) -> bool: ...


class _FallbackTieredCacheManager:
    """Minimal in-memory cache stub (no Redis/external tiers)."""

    def __init__(self, **kwargs: Any) -> None:
        self._local: dict[str, Any] = {}
        self.default_ttl: int = int(kwargs.get("default_ttl", 300))

    async def get(self, key: str) -> Any | None:
        return self._local.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        del ttl
        self._local[key] = value

    async def delete(self, key: str) -> None:
        self._local.pop(key, None)

    async def clear(self) -> None:
        self._local.clear()

    async def has(self, key: str) -> bool:
        return key in self._local


class _FallbackTieredCacheConfig:
    """Minimal config stub for fallback cache."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


_shared_cache_manager: Any | None = None
try:
    from src.core.shared.cache import manager as _shared_cache_manager_module
except ImportError:
    pass
else:
    _shared_cache_manager = _shared_cache_manager_module

if _shared_cache_manager is not None:
    TieredCacheManager = cast(Any, _shared_cache_manager.TieredCacheManager)
    TieredCacheConfig = cast(Any, getattr(_shared_cache_manager, "TieredCacheConfig", None))
    get_cache_manager = cast(Any, getattr(_shared_cache_manager, "get_cache_manager", None))
else:
    TieredCacheManager = _FallbackTieredCacheManager
    TieredCacheConfig = _FallbackTieredCacheConfig

    def get_cache_manager(**kwargs: Any) -> _CacheManagerProtocol:
        return _FallbackTieredCacheManager(**kwargs)


__all__ = [
    "TieredCacheConfig",
    "TieredCacheManager",
    "get_cache_manager",
]
