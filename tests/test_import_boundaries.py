"""Import-boundary checks for enhanced_agent_bus.

enhanced_agent_bus is a service-package. It may import from acgs_lite,
src.core.shared, and acgs_deliberation. It must not import from:
  - constitutional_swarm (EAB optionally imports swarm; swarm must not import EAB)
  - mhc (lateral/higher-level)

The _compat/ subpackage intentionally re-exports src.core.shared.* during the
migration away from the monolith namespace — those imports are excluded from
this check.

KNOWN_VIOLATIONS tracks existing debt. The test fails when:
  - a NEW violation appears (add to KNOWN_VIOLATIONS after review), or
  - a KNOWN violation disappears (remove from the set — debt paid off).
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PREFIXES = (
    "constitutional_swarm",
    "mhc",
)

# Pre-existing violations being tracked.
# governance_core.py imports constitutional_swarm dynamically and optionally
# (SWARM_AVAILABLE flag); the scanner sees it via string-literal import_module().
KNOWN_VIOLATIONS: set[str] = {
    # optional dynamic import, governance_core.py:40; SWARM_AVAILABLE flag
    "governance_core.py: constitutional_swarm",
}


def _iter_imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is not None:
                imports.append(node.module)
        elif isinstance(node, ast.Call):
            module = _dynamic_import_target(node)
            if module is not None:
                imports.append(module)
    return imports


def _dynamic_import_target(node: ast.Call) -> str | None:
    """Return the module for ``import_module("x")``, ``importlib.import_module("x")``
    or ``__import__("x")`` when the first argument is a string literal."""
    func = node.func
    is_bare = isinstance(func, ast.Name) and func.id in ("import_module", "__import__")
    is_qualified = (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id == "importlib"
    )
    if not (is_bare or is_qualified) or not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _is_excluded(path: Path) -> bool:
    """Skip test files and the _compat shim (intentional re-export layer)."""
    parts = path.parts
    return (
        "test" in path.name
        or path.name.startswith("_test")
        or "tests" in parts
        or "_compat" in parts
    )


def test_runtime_source_import_boundaries() -> None:
    found: set[str] = set()

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        rel = path.relative_to(SOURCE_ROOT)
        key_prefix = str(rel)

        for module in _iter_imports(path):
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    found.add(f"{key_prefix}: {module}")
                    break

    new_violations = found - KNOWN_VIOLATIONS
    cleared_violations = KNOWN_VIOLATIONS - found

    messages: list[str] = []
    if new_violations:
        messages.append(
            "NEW boundary violations (fix or add to KNOWN_VIOLATIONS with review comment):\n"
            + "\n".join(f"  {v}" for v in sorted(new_violations))
        )
    if cleared_violations:
        messages.append(
            "Violations no longer present — remove from KNOWN_VIOLATIONS:\n"
            + "\n".join(f"  {v}" for v in sorted(cleared_violations))
        )

    assert not messages, "\n\n".join(messages)


def test_iter_imports_sees_dynamic_import(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text('from importlib import import_module\nx = import_module("constitutional_swarm")\n')
    assert "constitutional_swarm" in _iter_imports(f)


def test_iter_imports_ignores_non_literal_dynamic_import(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text(
        "from importlib import import_module\n"
        'name = "constitutional_swarm"\n'
        "x = import_module(name)\n"
        'y = import_module(f"{name}.mesh")\n'
    )
    assert _iter_imports(f) == ["importlib"]


def test_iter_imports_sees_qualified_dynamic_import(tmp_path: Path) -> None:
    f = tmp_path / "m.py"
    f.write_text('import importlib\nx = importlib.import_module("constitutional_swarm.mesh")\n')
    assert "constitutional_swarm.mesh" in _iter_imports(f)
