"""
AgentBrowserTool FastMCP server — browser automation for MCP-native clients.
Constitutional hash: 608508a9bd224290

Exposes agent-browser CLI automation via 4 MCP tools:
  - browser_snapshot   — accessibility tree snapshot of a URL
  - browser_click      — click element by ref
  - browser_type       — type text into element by ref
  - browser_navigate   — navigate to URL

The server fails gracefully when the agent-browser binary is not on PATH —
all tools return an error dict rather than raising or crashing the server.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from enhanced_agent_bus.tools.agent_browser_tool import (
    AgentBrowserTool,
    AgentBrowserUnavailableError,
    is_available,
)

try:
    from mcp.server import Server

    from mcp import types

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    Server = None  # type: ignore[assignment,misc]

_CONSTITUTIONAL_HASH = "608508a9bd224290"
_SERVER_NAME = "acgs-browser"

logger = structlog.get_logger(__name__).bind(
    constitutional_hash=_CONSTITUTIONAL_HASH,
    server=_SERVER_NAME,
)

# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

_browser_tool: AgentBrowserTool | None = None


def _get_tool() -> AgentBrowserTool | None:
    """Return the module-level AgentBrowserTool, creating it on first call.

    Returns None (and logs a warning) when the binary is not available.
    """
    global _browser_tool  # noqa: PLW0603
    if _browser_tool is not None:
        return _browser_tool
    if not is_available():
        logger.warning(
            "agent_browser_unavailable",
            message="agent-browser binary not found; all browser tools disabled",
        )
        return None
    try:
        _browser_tool = AgentBrowserTool(agent_id=_SERVER_NAME)
    except AgentBrowserUnavailableError as exc:
        logger.warning(
            "agent_browser_init_failed",
            error=type(exc).__name__,
        )
        return None
    return _browser_tool


def _unavailable_error() -> dict[str, str]:
    return {
        "error": "AgentBrowserUnavailableError",
        "message": "agent-browser binary not found on PATH; install with: cargo install agent-browser",
    }


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_browser_server(*, server_name: str = _SERVER_NAME) -> Any:
    """Create and return the FastMCP server instance.

    Args:
        server_name: Name reported to MCP clients.

    Returns:
        MCP Server object.

    Raises:
        ImportError: When the ``mcp`` package is not installed.
    """
    if not MCP_AVAILABLE:
        raise ImportError("mcp package is required; install with: pip install mcp")

    server = Server(server_name)

    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="browser_snapshot",
                description=(
                    "Capture an accessibility tree snapshot of a URL. "
                    "Returns element refs for use with browser_click and browser_type."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Page URL to snapshot"},
                    },
                    "required": ["url"],
                },
            ),
            types.Tool(
                name="browser_click",
                description="Click an element identified by its accessibility-tree ref.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref": {
                            "type": "string",
                            "description": "Stable element ref from a prior browser_snapshot",
                        },
                    },
                    "required": ["ref"],
                },
            ),
            types.Tool(
                name="browser_type",
                description="Type text into an element identified by its accessibility-tree ref.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ref": {
                            "type": "string",
                            "description": "Stable element ref from a prior browser_snapshot",
                        },
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["ref", "text"],
                },
            ),
            types.Tool(
                name="browser_navigate",
                description="Navigate to a URL and confirm navigation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "Destination URL"},
                    },
                    "required": ["url"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    return server


async def _dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route an MCP tool call to the underlying AgentBrowserTool method."""
    tool = _get_tool()

    if tool is None:
        return _unavailable_error()

    try:
        if name == "browser_snapshot":
            url = arguments.get("url", "")
            snap = await tool.snapshot(url)
            return snap.model_dump()

        if name == "browser_click":
            ref = arguments.get("ref", "")
            res = await tool.click(ref)
            return res.model_dump()

        if name == "browser_type":
            ref = arguments.get("ref", "")
            text = arguments.get("text", "")
            res = await tool.type_text(ref, text)
            return res.model_dump()

        if name == "browser_navigate":
            url = arguments.get("url", "")
            res = await tool.navigate(url)
            return res.model_dump()

        return {"error": "UnknownToolError", "message": f"No such tool: {name}"}

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "browser_tool_call_failed",
            tool=name,
            error=type(exc).__name__,
        )
        return {
            "error": type(exc).__name__,
            "message": "Browser tool call failed; check server logs for details",
        }


__all__ = ["create_browser_server"]
