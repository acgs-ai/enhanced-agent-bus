"""Ratchet: the source distribution ships the sources, not the test suite.

The explicit ``[tool.setuptools] packages`` list keeps tests out of the wheel and
says nothing about the sdist, which setuptools builds by walking the package
directory — and ``package-dir = {enhanced_agent_bus = "."}`` makes that the whole
repository root. Measured from a clean checkout before MANIFEST.in existed: 1522
members, 3.4 MB, 513 of them test files.

Two failure directions, one test each. Ship too much and the archive carries the
suite again; prune too hard and the sdist can no longer produce the wheel.
``test_sdist_ships_every_non_test_module`` is the second guard — it is what makes
a hand-written prune list safe to keep.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest

from . import _module_walk

PKG_ROOT = _module_walk.PKG_ROOT
MANIFEST = PKG_ROOT / "MANIFEST.in"
_BUILD_TIMEOUT_SECONDS = 900


@pytest.fixture(scope="module")
def sdist_members() -> list[str]:
    """Build an sdist and return its member paths, relative to the archive root."""

    if shutil.which("uv") is None:
        pytest.skip("uv is not available; `python -m build` needs pip, absent from the uv venv")
    with tempfile.TemporaryDirectory() as out:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["uv", "build", "--sdist", "--out-dir", out, str(PKG_ROOT)],
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        assert completed.returncode == 0, f"sdist build failed:\n{completed.stderr[-2000:]}"
        archives = sorted(Path(out).glob("*.tar.gz"))
        assert len(archives) == 1, f"expected one sdist, got {[a.name for a in archives]}"
        with tarfile.open(archives[0]) as tar:
            names = tar.getnames()
    # Members are prefixed with the "<name>-<version>/" root directory.
    return [name.split("/", 1)[1] for name in names if "/" in name]


def test_manifest_exists_and_prunes_the_test_tree() -> None:
    """The cheap half of the guard: it still runs when uv is unavailable.

    Deliberately checks only the top-level tests/ line. The per-package tests
    directories are not listed packages, so setuptools never collects them and
    pruning them is a no-op — asserting on those lines would fail contributors
    for omitting something that has no effect.
    """

    assert MANIFEST.is_file(), f"{MANIFEST} is missing; the sdist would ship the test suite"
    lines = {line.strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines()}
    assert "prune tests" in lines, (
        "MANIFEST.in does not prune the top-level tests/ tree; the sdist would carry "
        "the suite (513 files when this was measured)."
    )


def test_sdist_ships_no_tests(sdist_members: list[str]) -> None:
    """A published sdist must not carry the test suite."""

    tests = sorted(name for name in sdist_members if "/tests/" in name or name.startswith("tests/"))
    assert not tests, (
        f"{len(tests)} test file(s) in the sdist. Add a `prune <dir>` line to MANIFEST.in "
        "for the owning directory; `prune` takes a literal path, not a glob.\n  "
        + "\n  ".join(tests[:20])
    )


def test_sdist_ships_every_non_test_module(sdist_members: list[str]) -> None:
    """The other direction: an over-broad exclusion breaks building the wheel from the sdist.

    Scoped honestly. ``prune <package-dir>`` cannot trigger this — setuptools re-adds
    package sources and package-data after MANIFEST.in is processed, verified by
    pruning ``api`` and ``policies`` and watching the archive not change. What it does
    catch is the exclude-shaped mistake: adding ``global-exclude *.py`` fails here and
    nowhere else.
    """

    shipped = set(sdist_members)
    missing = []
    for source in PKG_ROOT.rglob("*.py"):
        relative = source.relative_to(PKG_ROOT)
        if any(part in _module_walk.EXCLUDED_DIRS for part in relative.parts):
            continue
        if relative.as_posix() not in shipped:
            missing.append(relative.as_posix())
    assert not missing, (
        f"{len(missing)} non-test module(s) exist in the tree but not in the sdist. "
        "A prune line is too broad:\n  " + "\n  ".join(sorted(missing)[:20])
    )


def test_sdist_ships_the_build_inputs(sdist_members: list[str]) -> None:
    """Without these the archive cannot rebuild the wheel it is supposed to produce."""

    shipped = set(sdist_members)
    required = {"pyproject.toml", "README.md", "MANIFEST.in", "py.typed"}
    assert required <= shipped, f"sdist is missing build inputs: {sorted(required - shipped)}"
    rego = [name for name in sdist_members if name.endswith(".rego")]
    assert len(rego) == 12, (
        f"expected the 12 declared policy files ([tool.setuptools.package-data]), got {len(rego)}"
    )
