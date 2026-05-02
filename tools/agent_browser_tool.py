"""Agent Browser CLI wrapper used by MCP browser automation.

The wrapper is intentionally small: it detects the optional ``agent-browser``
binary, runs commands asynchronously, and normalizes JSON output into stable
Pydantic models for the FastMCP server.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from typing import Any

from pydantic import BaseModel, Field

try:
    from enhanced_agent_bus._compat.constants import CONSTITUTIONAL_HASH
except ImportError:
    CONSTITUTIONAL_HASH = "608508a9bd224290"


class AgentBrowserUnavailableError(RuntimeError):
    """Raised when the optional agent-browser binary is unavailable."""


class AgentBrowserCommandError(RuntimeError):
    """Raised when agent-browser exits unsuccessfully or returns invalid output."""


class BrowserElement(BaseModel):
    """Accessibility-tree element returned by agent-browser snapshots."""

    ref: str
    role: str | None = None
    name: str | None = None
    value: Any | None = None
    bounds: Any | None = None
    children: list["BrowserElement"] = Field(default_factory=list)


class BrowserSnapshot(BaseModel):
    """Normalized snapshot result for MCP clients."""

    url: str
    title: str | None = None
    elements: list[BrowserElement] = Field(default_factory=list)
    latency_ms: float = 0.0
    constitutional_hash: str = CONSTITUTIONAL_HASH
    raw: dict[str, Any] = Field(default_factory=dict)


class BrowserActionResult(BaseModel):
    """Normalized click/type/navigate result for MCP clients."""

    success: bool
    url: str | None = None
    error: str | None = None
    latency_ms: float = 0.0
    constitutional_hash: str = CONSTITUTIONAL_HASH
    raw: dict[str, Any] = Field(default_factory=dict)


def is_available(binary_path: str = "agent-browser") -> bool:
    """Return whether the optional agent-browser CLI is available."""

    return shutil.which(binary_path) is not None


class AgentBrowserTool:
    """Async wrapper around the optional agent-browser CLI."""

    def __init__(
        self,
        *,
        agent_id: str,
        binary_path: str = "agent-browser",
        timeout_s: float = 30.0,
    ) -> None:
        if not is_available(binary_path):
            raise AgentBrowserUnavailableError("agent-browser binary is not available")

        self.agent_id = agent_id
        self.binary_path = binary_path
        self.timeout_s = timeout_s

    async def snapshot(self, url: str) -> BrowserSnapshot:
        """Return an accessibility-tree snapshot for *url*."""

        start = time.monotonic()
        payload = await self._run_json("snapshot", url)
        latency_ms = (time.monotonic() - start) * 1000
        return BrowserSnapshot(
            url=str(payload.get("url") or url),
            title=payload.get("title"),
            elements=[BrowserElement.model_validate(item) for item in payload.get("elements", [])],
            latency_ms=latency_ms,
            raw=payload,
        )

    async def click(self, ref: str) -> BrowserActionResult:
        """Click an element by accessibility-tree reference."""

        return await self._action("click", ref)

    async def type_text(self, ref: str, text: str) -> BrowserActionResult:
        """Type text into an element by accessibility-tree reference."""

        return await self._action("type", ref, text)

    async def navigate(self, url: str) -> BrowserActionResult:
        """Navigate the current browser session to *url*."""

        return await self._action("navigate", url)

    async def _action(self, *args: str) -> BrowserActionResult:
        start = time.monotonic()
        payload = await self._run_json(*args)
        latency_ms = (time.monotonic() - start) * 1000
        return BrowserActionResult(
            success=bool(payload.get("success", True)),
            url=payload.get("url"),
            error=payload.get("error"),
            latency_ms=latency_ms,
            raw=payload,
        )

    async def _run_json(self, *args: str) -> dict[str, Any]:
        command = [self.binary_path, *args, "--json"]
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise AgentBrowserUnavailableError("agent-browser binary is not available") from exc

        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_s)
        except TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise AgentBrowserCommandError("agent-browser command timed out") from exc

        if proc.returncode != 0:
            raise AgentBrowserCommandError("agent-browser command failed")

        try:
            payload = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentBrowserCommandError("agent-browser returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise AgentBrowserCommandError("agent-browser returned non-object JSON")

        return payload


__all__ = [
    "AgentBrowserCommandError",
    "AgentBrowserTool",
    "AgentBrowserUnavailableError",
    "BrowserActionResult",
    "BrowserElement",
    "BrowserSnapshot",
    "is_available",
]
