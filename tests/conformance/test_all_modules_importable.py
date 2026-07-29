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
_ENV_DIRECTIVE = "# baseline-env:"


def load_allowlist() -> set[str]:
    """Return the recorded known-failing module names."""

    entries: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def load_baseline_env() -> dict[str, str]:
    """Return the installed-dependency set the allowlist was recorded against."""

    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(_ENV_DIRECTIVE):
            body = stripped[len(_ENV_DIRECTIVE) :]
            return dict(token.split("=", 1) for token in body.split())
    raise AssertionError(
        f"{ALLOWLIST_PATH.name} has no '{_ENV_DIRECTIVE}' line. The allowlist is only "
        "meaningful for one installed dependency set; record it."
    )


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


def test_environment_matches_recorded_baseline(walk_report: dict[str, object]) -> None:
    """The allowlist is only valid for the dependency set it was recorded against.

    Installing an extra makes previously-unimportable modules import, which the
    drift test would otherwise report as remediation progress made by nobody.
    Fail here first, naming the dependency, so the cause is unambiguous.
    """

    observed: dict[str, str] = walk_report["env"]  # type: ignore[assignment]
    expected = load_baseline_env()
    differences = sorted(
        f"{name}: baseline assumed {state}, found {observed.get(name, 'unknown')}"
        for name, state in expected.items()
        if observed.get(name) != state
    )
    assert not differences, (
        "installed dependency set differs from the one known_import_failures.txt was "
        "recorded against, so its counts are not comparable:\n  "
        + "\n  ".join(differences)
        + "\n\nEither install the recorded set, or re-record the allowlist and update "
        f"its '{_ENV_DIRECTIVE}' line in the same commit."
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
        "known_import_failures.txt. If a remediation phase fixed them, delete these "
        "lines and record the delta in the PR description. If you installed an extra, "
        "test_environment_matches_recorded_baseline names the dependency:\n  "
        + "\n  ".join(fixed)
    )
