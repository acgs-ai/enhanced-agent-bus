"""Ratchet: the built wheel ships the package and nothing but the package.

``package-dir = {enhanced_agent_bus = "."}`` makes the whole repository the
package, so every test directory shipped until ``[tool.setuptools] packages``
was made explicit — measured before that change: 1823 files, 5.7 MB, 942 of
them under a ``tests/`` path (52% of the wheel).

An explicit package list rots: a new subpackage is silently dropped from the
wheel until someone remembers to add it. ``test_wheel_ships_every_non_test_module``
is the counterweight — it diffs the wheel against the source tree.
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile

import pytest

from . import _module_walk

PKG_ROOT = _module_walk.PKG_ROOT
_BUILD_TIMEOUT_SECONDS = 900


@pytest.fixture(scope="module")
def wheel_members(tmp_path_factory: pytest.TempPathFactory) -> list[str]:
    """Build a wheel and return its member paths."""

    if shutil.which("uv") is None:
        pytest.skip("uv is not available; `python -m build` needs pip, absent from the uv venv")
    out = tmp_path_factory.mktemp("wheel")
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["uv", "build", "--wheel", "--out-dir", str(out), str(PKG_ROOT)],
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )
    assert completed.returncode == 0, f"wheel build failed:\n{completed.stderr[-2000:]}"
    wheels = sorted(out.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {[w.name for w in wheels]}"
    with zipfile.ZipFile(wheels[0]) as archive:
        return archive.namelist()


def test_wheel_ships_no_tests(wheel_members: list[str]) -> None:
    """A published wheel must not carry the test suite."""

    tests = sorted(name for name in wheel_members if "/tests/" in name or name.startswith("tests/"))
    assert not tests, (
        f"{len(tests)} test file(s) in the wheel. `[tool.setuptools] packages` must list "
        "the shipped packages explicitly; note that `[tool.setuptools.packages.find]` is "
        "NOT usable here — with package-dir = {enhanced_agent_bus = '.'} it discovers "
        "unprefixed names and ships api/, bus/, ... as top-level packages.\n  "
        + "\n  ".join(tests[:20])
    )


def test_wheel_ships_only_the_package(wheel_members: list[str]) -> None:
    """Everything must live under enhanced_agent_bus/ — no stray top-level packages."""

    tops = {
        name.split("/", 1)[0]
        for name in wheel_members
        if "/" in name and not name.split("/", 1)[0].endswith(".dist-info")
    }
    assert tops == {"enhanced_agent_bus"}, (
        f"wheel ships unexpected top-level entries: {sorted(tops - {'enhanced_agent_bus'})}. "
        "This is the packages.find failure mode — `import enhanced_agent_bus` would break "
        "and the names would collide with unrelated distributions."
    )


def test_wheel_ships_every_non_test_module(wheel_members: list[str]) -> None:
    """Explicit package lists rot: a new subpackage is silently dropped until listed."""

    shipped = {name for name in wheel_members if name.endswith(".py")}
    missing = []
    for source in PKG_ROOT.rglob("*.py"):
        relative = source.relative_to(PKG_ROOT)
        if any(part in _module_walk.EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.parts[-1] in _module_walk.EXCLUDED_BASENAMES:
            continue
        if f"enhanced_agent_bus/{relative.as_posix()}" not in shipped:
            missing.append(relative.as_posix())
    assert not missing, (
        f"{len(missing)} non-test module(s) exist in the tree but not in the wheel. "
        "Add the owning package to `[tool.setuptools] packages`:\n  "
        + "\n  ".join(sorted(missing)[:20])
    )
