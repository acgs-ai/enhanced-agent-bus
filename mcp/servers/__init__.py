"""Optional MCP server entry points."""

from . import browser_server as browser_server
from .browser_server import create_browser_server

__all__ = ["browser_server", "create_browser_server"]
