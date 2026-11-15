"""Regression tests for optional extension shim fallback exports."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType


def test_top_level_package_imports_with_metrics_fallback() -> None:
    module = importlib.import_module("enhanced_agent_bus")

    assert module.__version__ == "3.1.0"


def test_standalone_database_session_fallback_provides_orm_base() -> None:
    session_module = importlib.import_module("enhanced_agent_bus._compat.database.session")

    assert session_module.Base is not None


@contextmanager
def _reimport_with_blocked_dependency(
    module_name: str,
    dependency_name: str,
) -> Iterator[ModuleType]:
    """Re-import a shim module while forcing its dependency import to fail."""

    original_module = sys.modules.pop(module_name, None)
    dependency_present = dependency_name in sys.modules
    original_dependency = sys.modules.get(dependency_name)
    sys.modules[dependency_name] = None  # type: ignore[assignment]

    try:
        module = importlib.import_module(module_name)
        yield importlib.reload(module)
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module

        if dependency_present:
            sys.modules[dependency_name] = original_dependency  # type: ignore[assignment]
        else:
            sys.modules.pop(dependency_name, None)


def test_ext_context_optimization_fallback_exports() -> None:
    with _reimport_with_blocked_dependency(
        "enhanced_agent_bus._ext_context_optimization",
        "enhanced_agent_bus.context_optimization",
    ) as module:
        assert module.CONTEXT_OPTIMIZATION_AVAILABLE is False

        none_exports = {
            "create_spec_compressor",
            "create_cached_validator",
            "create_optimized_bus",
        }
        for name in module.__all__:
            value = getattr(module, name)
            if name == "CONTEXT_OPTIMIZATION_AVAILABLE":
                assert value is False
            elif name in none_exports:
                assert value is None
            else:
                assert value is object

        assert module._EXT_ALL == module.__all__


def test_ext_performance_fallback_exports() -> None:
    with _reimport_with_blocked_dependency(
        "enhanced_agent_bus._ext_performance",
        "enhanced_agent_bus.performance_optimization",
    ) as module:
        assert module.PERFORMANCE_OPTIMIZATION_AVAILABLE is False

        none_exports = {
            "create_async_pipeline",
            "create_resource_pool",
            "create_memory_optimizer",
            "create_latency_reducer",
        }
        for name in module.__all__:
            value = getattr(module, name)
            if name == "PERFORMANCE_OPTIMIZATION_AVAILABLE":
                assert value is False
            elif name in none_exports:
                assert value is None
            else:
                assert value is object

        assert module._EXT_ALL == module.__all__


def test_standalone_database_session_base_none_when_sqlalchemy_absent() -> None:
    """Base=None when both shared-session and sqlalchemy.orm are unavailable."""
    module_name = "enhanced_agent_bus._compat.database.session"
    blocked = ["src.core.shared.database.session", "sqlalchemy.orm", "sqlalchemy"]

    originals = {k: sys.modules.get(k) for k in blocked}
    original_module = sys.modules.pop(module_name, None)
    for k in blocked:
        sys.modules[k] = None  # type: ignore[assignment]

    try:
        module = importlib.import_module(module_name)
        reloaded = importlib.reload(module)
        assert reloaded.Base is None
        assert reloaded.engine is None
        assert reloaded.SessionLocal is None
    finally:
        sys.modules.pop(module_name, None)
        if original_module is not None:
            sys.modules[module_name] = original_module
        for k, v in originals.items():
            if v is not None:
                sys.modules[k] = v
            else:
                sys.modules.pop(k, None)


def test_ext_circuit_breaker_fallback_exports() -> None:
    with _reimport_with_blocked_dependency(
        "enhanced_agent_bus._ext_circuit_breaker",
        "enhanced_agent_bus.circuit_breaker",
    ) as module:
        assert module.SERVICE_CIRCUIT_BREAKER_AVAILABLE is False

        for name in module._EXT_ALL:
            value = getattr(module, name)
            if name == "SERVICE_CIRCUIT_BREAKER_AVAILABLE":
                assert value is False
            elif name == "SERVICE_CIRCUIT_CONFIGS":
                assert value == {}
            else:
                assert value is object
