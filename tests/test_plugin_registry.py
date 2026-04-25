from __future__ import annotations

import pytest

from enhanced_agent_bus.plugin_registry import (
    EXT_MODULES,
    PLUGINS,
    PluginNotAvailable,
    available,
    load_status,
    require,
)


def test_available_known_dependency() -> None:
    assert available("numpy") is True


def test_require_returns_module_path_for_known_dependency() -> None:
    assert require("numpy") == "numpy"


def test_require_raises_with_install_hint_for_missing_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        __import__("enhanced_agent_bus.plugin_registry").plugin_registry.PLUGINS,
        "fake_plugin",
        "fake.module",
    )
    monkeypatch.setitem(
        __import__("enhanced_agent_bus.plugin_registry").plugin_registry.EXTRAS,
        "fake_plugin",
        "fake-extra",
    )

    with pytest.raises(PluginNotAvailable, match="pip install fake-extra"):
        require("fake_plugin")


def test_all_ext_modules_registered() -> None:
    expected = {
        "_ext_browser_tool",
        "_ext_cache_warming",
        "_ext_chaos",
        "_ext_circuit_breaker",
        "_ext_circuit_breaker_clients",
        "_ext_cognee",
        "_ext_cognitive",
        "_ext_context_memory",
        "_ext_context_optimization",
        "_ext_decision_store",
        "_ext_explanation_service",
        "_ext_langgraph",
        "_ext_mcp",
        "_ext_performance",
        "_ext_persistence",
        "_ext_pqc",
        "_ext_response_quality",
        "_ext_spacetimedb",
    }
    assert expected.issubset(set(PLUGINS)), f"Missing: {expected - set(PLUGINS)}"
    assert set(EXT_MODULES) == expected


def test_load_status_returns_bool_for_all() -> None:
    status = load_status()
    assert set(status.keys()) == set(EXT_MODULES)
    for ext, ok in status.items():
        assert isinstance(ok, bool), f"{ext} status is not bool: {type(ok)}"


def test_available_returns_false_for_nonexistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(PLUGINS, "_test_nonexistent_xyz", "enhanced_agent_bus._nonexistent_xyz")
    assert available("_test_nonexistent_xyz") is False
