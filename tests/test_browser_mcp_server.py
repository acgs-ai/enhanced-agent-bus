"""
Tests for the AgentBrowserTool FastMCP server.
Constitutional hash: 608508a9bd224290
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — minimal stubs for the mcp package types used by the server
# ---------------------------------------------------------------------------

# The mcp package may not be installed in all environments; use stubs when absent.
try:
    from mcp import types as mcp_types  # noqa: F401
    _MCP_INSTALLED = True
except ImportError:
    _MCP_INSTALLED = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SNAPSHOT_DATA: dict[str, Any] = {
    "url": "https://example.com",
    "title": "Example",
    "elements": [
        {
            "ref": "btn-1",
            "role": "button",
            "name": "Submit",
            "value": None,
            "bounds": None,
            "children": [],
        }
    ],
    "latency_ms": 42.0,
    "constitutional_hash": "608508a9bd224290",
    "raw": {},
}

_ACTION_DATA: dict[str, Any] = {
    "success": True,
    "url": "https://example.com",
    "error": None,
    "latency_ms": 10.0,
    "constitutional_hash": "608508a9bd224290",
    "raw": {},
}


def _make_snapshot_mock() -> MagicMock:
    snap = MagicMock()
    snap.model_dump.return_value = dict(_SNAPSHOT_DATA)
    return snap


def _make_action_mock() -> MagicMock:
    action = MagicMock()
    action.model_dump.return_value = dict(_ACTION_DATA)
    return action


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBrowserMcpServerDispatch:
    """Test _dispatch() directly — no MCP transport layer needed."""

    @pytest.mark.asyncio
    async def test_snapshot_success(self) -> None:
        snap_mock = _make_snapshot_mock()
        tool_mock = MagicMock()
        tool_mock.snapshot = AsyncMock(return_value=snap_mock)

        with (
            patch(
                "enhanced_agent_bus.mcp.servers.browser_server.is_available",
                return_value=True,
            ),
            patch(
                "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
                return_value=tool_mock,
            ),
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_snapshot", {"url": "https://example.com"})

        assert result["url"] == "https://example.com"
        assert result["title"] == "Example"
        tool_mock.snapshot.assert_awaited_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_snapshot_unavailable(self) -> None:
        with patch(
            "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
            return_value=None,
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_snapshot", {"url": "https://example.com"})

        assert result["error"] == "AgentBrowserUnavailableError"
        assert "message" in result

    @pytest.mark.asyncio
    async def test_click_success(self) -> None:
        action_mock = _make_action_mock()
        tool_mock = MagicMock()
        tool_mock.click = AsyncMock(return_value=action_mock)

        with patch(
            "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
            return_value=tool_mock,
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_click", {"ref": "btn-1"})

        assert result["success"] is True
        tool_mock.click.assert_awaited_once_with("btn-1")

    @pytest.mark.asyncio
    async def test_type_success(self) -> None:
        action_mock = _make_action_mock()
        tool_mock = MagicMock()
        tool_mock.type_text = AsyncMock(return_value=action_mock)

        with patch(
            "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
            return_value=tool_mock,
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_type", {"ref": "input-1", "text": "hello"})

        assert result["success"] is True
        tool_mock.type_text.assert_awaited_once_with("input-1", "hello")

    @pytest.mark.asyncio
    async def test_navigate_success(self) -> None:
        action_mock = _make_action_mock()
        tool_mock = MagicMock()
        tool_mock.navigate = AsyncMock(return_value=action_mock)

        with patch(
            "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
            return_value=tool_mock,
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_navigate", {"url": "https://other.com"})

        assert result["success"] is True
        tool_mock.navigate.assert_awaited_once_with("https://other.com")

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error_dict(self) -> None:
        tool_mock = MagicMock()
        tool_mock.snapshot = AsyncMock(side_effect=RuntimeError("subprocess died"))

        with patch(
            "enhanced_agent_bus.mcp.servers.browser_server._get_tool",
            return_value=tool_mock,
        ):
            from enhanced_agent_bus.mcp.servers.browser_server import _dispatch

            result = await _dispatch("browser_snapshot", {"url": "https://example.com"})

        # Must return an error dict, NOT raise
        assert "error" in result
        assert result["error"] == "RuntimeError"
        # Must never contain str(exc) content (security rule)
        assert "subprocess died" not in json.dumps(result)
