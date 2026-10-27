"""Static and runtime contracts for the standalone compatibility facades."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("facade, upstream, export", [
    ("_compat/constants.py", "src.core.shared.constants", "MACIRole"),
    ("_compat/types/__init__.py", "src.core.shared.types", "JSONDict"),
])
def test_upstream_exports_preserve_identity_and_fallbacks_remain_available(
    monkeypatch: pytest.MonkeyPatch, facade: str, upstream: str, export: str,
) -> None:
    monkeypatch.setitem(sys.modules, upstream, None)
    fallback = runpy.run_path(str(ROOT / facade))
    assert fallback["CONSTITUTIONAL_HASH"] == "608508a9bd224290"
    if export == "MACIRole":
        assert fallback[export].parse(" monitor ").value == "MONITOR"
    else:
        assert fallback[export](role="observer") == {"role": "observer"}

    # A real upstream package wins at runtime, including extra public exports.
    for name in ("src", "src.core", "src.core.shared"):
        package = ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
    module = ModuleType(upstream)
    for name, value in fallback.items():
        if not name.startswith("_"):
            setattr(module, name, value)
    sentinel = object()
    setattr(module, export, sentinel)
    module.EXTRA_UPSTREAM_EXPORT = sentinel
    monkeypatch.setitem(sys.modules, upstream, module)
    loaded = runpy.run_path(str(ROOT / facade))
    assert loaded[export] is sentinel
    assert loaded["EXTRA_UPSTREAM_EXPORT"] is sentinel


def test_static_consumers_keep_concrete_role_and_json_types(tmp_path: Path) -> None:
    pytest.importorskip("mypy")
    (tmp_path / "enhanced_agent_bus").symlink_to(ROOT, target_is_directory=True)
    imports = (
        "from enhanced_agent_bus._compat.constants import MACIRole, CONSTITUTIONAL_HASH\n"
        "from enhanced_agent_bus._compat.types import JSONDict\n"
    )
    env = {**os.environ, "MYPYPATH": str(tmp_path)}
    consumer = tmp_path / "consumer.py"
    command = [
        sys.executable, "-m", "mypy", "--config-file", str(ROOT / "mypy.ini"),
        "--cache-dir", str(tmp_path / "cache"), "--no-incremental", str(consumer),
    ]
    consumer.write_text(
        imports + "role: MACIRole = MACIRole.parse('monitor')\n"
        "payload: JSONDict = {'role': role.value}\n"
        "digest: str = CONSTITUTIONAL_HASH\n",
    )
    valid = subprocess.run(
        command,
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    assert valid.returncode == 0, valid.stdout + valid.stderr
    consumer.write_text(imports + "role = MACIRole.NOT_A_ROLE\npayload: JSONDict = []\n")
    invalid = subprocess.run(
        command,
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    assert invalid.returncode == 1, invalid.stdout + invalid.stderr
    assert '[attr-defined]' in invalid.stdout
    assert '[assignment]' in invalid.stdout
    assert 'Found 2 errors' in invalid.stdout
