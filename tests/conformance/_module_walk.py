"""Walk every module in the package and import it, reporting the outcome as JSON.

Run as a subprocess (see ``test_all_modules_importable``) so that importing ~850
modules — which starts threads, configures logging and installs signal handlers —
cannot contaminate the pytest process.

    python -m enhanced_agent_bus.tests.conformance._module_walk
    python <path-to-this-file>
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[2]
PKG_NAME = "enhanced_agent_bus"

#: Directory names pruned from the walk anywhere in the path.
#:
#: ``tests``/``migrations``/``__pycache__`` are the mandated exclusions. The rest
#: are build, cache and vendor trees that contain no first-party modules.
EXCLUDED_DIRS = frozenset(
    {
        "tests",
        "migrations",
        "__pycache__",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "rust",
        "venv",
    }
)

#: Files excluded by name. ``conftest.py`` is pytest plumbing, not a package
#: module. Root-level ``eval_*.py`` are benchmark harnesses that execute
#: subprocess timing loops at import; importing them is a side effect, not a
#: conformance signal.
EXCLUDED_BASENAMES = frozenset({"conftest.py"})
EXCLUDED_ROOT_PREFIXES = ("eval_",)


def dotted_name(relative: Path) -> str:
    """Return the dotted module name a source path is imported under."""

    parts = relative.parts
    if parts[-1] == "__init__.py":
        stem_parts = parts[:-1]
    else:
        stem_parts = (*parts[:-1], parts[-1][: -len(".py")])
    return ".".join((PKG_NAME, *stem_parts))


def discover(root: Path = PKG_ROOT) -> list[str]:
    """Return every dotted module name reachable under ``root``, sorted."""

    names: set[str] = set()
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
            continue
        basename = relative.parts[-1]
        if basename in EXCLUDED_BASENAMES:
            continue
        if len(relative.parts) == 1 and basename.startswith(EXCLUDED_ROOT_PREFIXES):
            continue
        names.add(dotted_name(relative))
    return sorted(names)


def walk() -> dict[str, object]:
    """Import every discovered module and return a JSON-serialisable report."""

    names = discover()
    failures: dict[str, str] = {}
    for name in names:
        try:
            importlib.import_module(name)
        except BaseException as exc:  # noqa: BLE001 - any failure is a finding
            detail = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
            failures[name] = detail[:200]
    return {"total": len(names), "importable": len(names) - len(failures), "failures": failures}


if __name__ == "__main__":
    sys.stdout.write("\n__CONFORMANCE_JSON__" + json.dumps(walk()) + "\n")
