"""Check every `_compat` shim against what its callers actually import and use.

Name existence alone is not a contract. ``_compat/feature_flags.py`` exposes
``FEATURES`` as a ``dict`` in its fallback branch while callers write
``FEATURES.mamba_enabled``: the name is present, the type is wrong, and twelve
modules die at import. So this collector records three obligations per import
site and checks all of them:

* the shim module imports at all;
* the imported name exists on it;
* the object supports the attribute access and call syntax callers use.

Run as a subprocess (see ``test_compat_contracts``) so importing the shim layer
cannot contaminate the pytest process.

    python <path-to-this-file>
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path

if __package__:
    from ._module_walk import EXCLUDED_DIRS, PKG_NAME, PKG_ROOT
else:  # executed directly as a subprocess entry point
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _module_walk import EXCLUDED_DIRS, PKG_NAME, PKG_ROOT  # type: ignore[no-redef]

COMPAT_PREFIX = f"{PKG_NAME}._compat"

#: Directories pruned from the AST scan. Unlike the import walk, `tests/` is
#: scanned: test-only callers are still callers, and the handoff requires the
#: shims they exercise to be either completed or their tests deleted.
SCAN_EXCLUDED_DIRS = EXCLUDED_DIRS - {"tests"}

#: Attribute names present on every object; accessing them proves nothing.
_UNIVERSAL_ATTRS = frozenset(dir(object())) | {"__dict__", "__module__", "__doc__"}


def source_files(root: Path = PKG_ROOT):
    """Yield every first-party source file, including tests."""

    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part in SCAN_EXCLUDED_DIRS for part in relative.parts[:-1]):
            continue
        yield path


def absolute_target(node: ast.ImportFrom, path: Path) -> str | None:
    """Resolve an ``ImportFrom`` to a dotted module, or None if it is not a shim."""

    if node.level == 0:
        module = node.module or ""
        return module if module.startswith(COMPAT_PREFIX) else None

    package_parts = list(path.relative_to(PKG_ROOT).parts[:-1])
    if node.level > 1:
        trim = node.level - 1
        package_parts = package_parts[:-trim] if trim <= len(package_parts) else []
    module = ".".join(
        [PKG_NAME, *package_parts, *(node.module.split(".") if node.module else [])]
    )
    return module if module.startswith(COMPAT_PREFIX) else None


def collect_obligations() -> dict[str, dict[str, dict[str, object]]]:
    """Return ``{shim: {name: {"attrs": [...], "called": bool}}}`` across the repo."""

    obligations: dict[str, dict[str, dict[str, object]]] = {}

    for path in source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

        bindings: dict[str, tuple[str, str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            shim = absolute_target(node, path)
            if shim is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                obligations.setdefault(shim, {}).setdefault(
                    alias.name, {"attrs": set(), "called": False}
                )
                bindings[alias.asname or alias.name] = (shim, alias.name)

        if not bindings:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                binding = bindings.get(node.value.id)
                if binding and node.attr not in _UNIVERSAL_ATTRS:
                    obligations[binding[0]][binding[1]]["attrs"].add(node.attr)  # type: ignore[union-attr]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                binding = bindings.get(node.func.id)
                if binding:
                    obligations[binding[0]][binding[1]]["called"] = True

    return obligations


def _resolves_as_submodule(shim: str, name: str) -> bool:
    """True when ``from shim import name`` works because ``name`` is a submodule."""

    try:
        importlib.import_module(f"{shim}.{name}")
    except BaseException:  # noqa: BLE001
        return False
    return True


def check() -> dict[str, object]:
    """Import each shim, verify every obligation, return a JSON-serialisable report."""

    obligations = collect_obligations()
    gaps: list[str] = []
    clean_shims = 0

    for shim in sorted(obligations):
        try:
            module = importlib.import_module(shim)
        except BaseException as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()
            gaps.append(f"{shim} :: <module> :: unimportable :: {detail[:160]}")
            continue

        shim_gaps: list[str] = []
        for name in sorted(obligations[shim]):
            entry = obligations[shim][name]
            if not hasattr(module, name):
                if _resolves_as_submodule(shim, name):
                    continue
                shim_gaps.append(f"{shim} :: {name} :: missing-name")
                continue
            obj = getattr(module, name)
            for attr in sorted(entry["attrs"]):  # type: ignore[arg-type]
                if not hasattr(obj, attr):
                    shim_gaps.append(
                        f"{shim} :: {name} :: missing-attr:{attr} :: got {type(obj).__name__}"
                    )
            if entry["called"] and not callable(obj):
                shim_gaps.append(
                    f"{shim} :: {name} :: not-callable :: got {type(obj).__name__}"
                )

        if shim_gaps:
            gaps.extend(shim_gaps)
        else:
            clean_shims += 1

    return {
        "shims_targeted": len(obligations),
        "clean": clean_shims,
        "with_gaps": len(obligations) - clean_shims,
        "gaps": sorted(gaps),
    }


if __name__ == "__main__":
    sys.stdout.write("\n__CONFORMANCE_JSON__" + json.dumps(check()) + "\n")
