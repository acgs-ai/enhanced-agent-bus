"""Ratchet: no module may regress into the known-import-failure allowlist.

The standalone extraction left a block of modules that cannot be imported —
missing runtime dependencies, `_compat` shims that do not satisfy their callers,
and direct `src.core.*` imports that have no standalone equivalent. That set is
recorded in ``known_import_failures.txt``. This test asserts the *observed*
failing set is a subset of the recorded one, so remediation deletes lines and
regressions fail the build.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from . import _module_walk

ALLOWLIST_PATH = Path(__file__).parent / "known_import_failures.txt"
_JSON_MARKER = "__CONFORMANCE_JSON__"
_WALK_TIMEOUT_SECONDS = 900


def load_allowlist() -> set[str]:
    """Return the recorded known-failing module names."""

    entries: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def run_walk() -> dict[str, object]:
    """Import every package module in a subprocess and return its report."""

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(Path(_module_walk.__file__).resolve())],
        capture_output=True,
        text=True,
        timeout=_WALK_TIMEOUT_SECONDS,
        cwd=str(_module_walk.PKG_ROOT),
    )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(_JSON_MARKER):
            return json.loads(line[len(_JSON_MARKER) :])
    raise AssertionError(
        "module walk produced no report\n"
        f"exit={completed.returncode}\n"
        f"stdout tail:\n{completed.stdout[-2000:]}\n"
        f"stderr tail:\n{completed.stderr[-2000:]}"
    )


@pytest.fixture(scope="module")
def walk_report() -> dict[str, object]:
    return run_walk()


def test_allowlist_is_well_formed() -> None:
    """Every allowlist entry must name a module the walk actually discovers."""

    discovered = set(_module_walk.discover())
    unknown = sorted(load_allowlist() - discovered)
    assert not unknown, (
        "known_import_failures.txt names modules that no longer exist; "
        "delete these lines:\n  " + "\n  ".join(unknown)
    )


def test_no_new_import_failures(walk_report: dict[str, object]) -> None:
    """The observed failing set must be a subset of the recorded allowlist."""

    failures: dict[str, str] = walk_report["failures"]  # type: ignore[assignment]
    regressions = sorted(set(failures) - load_allowlist())
    assert not regressions, (
        f"{len(regressions)} module(s) regressed into an import failure "
        f"(total={walk_report['total']}, importable={walk_report['importable']}):\n  "
        + "\n  ".join(f"{name} -> {failures[name]}" for name in regressions)
    )


def test_report_allowlist_drift(walk_report: dict[str, object]) -> None:
    """Surface allowlist entries that now import — they are the remediation delta."""

    failures: dict[str, str] = walk_report["failures"]  # type: ignore[assignment]
    fixed = sorted(load_allowlist() - set(failures))
    assert not fixed, (
        f"{len(fixed)} module(s) now import but are still listed in "
        "known_import_failures.txt. Delete these lines and record the delta in "
        "the PR description:\n  " + "\n  ".join(fixed)
    )
