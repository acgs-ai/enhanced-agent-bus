"""Ratchet: no `_compat` shim may regress against what its callers import and use.

A shim that imports cleanly but omits a name — or exposes a name of the wrong
kind — is worse than a missing module: the caller's `except ImportError` guard
never fires, so the failure surfaces as an `AttributeError` deep in a call path
instead of at the seam. ``known_shim_gaps.txt`` records the gaps present at
extraction time; remediation deletes lines from it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from . import _shim_contract

ALLOWLIST_PATH = Path(__file__).parent / "known_shim_gaps.txt"
_JSON_MARKER = "__CONFORMANCE_JSON__"
_CHECK_TIMEOUT_SECONDS = 900


def load_allowlist() -> set[str]:
    """Return the recorded known shim gaps."""

    entries: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            entries.add(stripped)
    return entries


def run_check() -> dict[str, object]:
    """Verify every shim obligation in a subprocess and return the report."""

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(Path(_shim_contract.__file__).resolve())],
        capture_output=True,
        text=True,
        timeout=_CHECK_TIMEOUT_SECONDS,
        cwd=str(_shim_contract.PKG_ROOT),
    )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(_JSON_MARKER):
            return json.loads(line[len(_JSON_MARKER) :])
    raise AssertionError(
        "shim contract check produced no report\n"
        f"exit={completed.returncode}\n"
        f"stdout tail:\n{completed.stdout[-2000:]}\n"
        f"stderr tail:\n{completed.stderr[-2000:]}"
    )


@pytest.fixture(scope="module")
def contract_report() -> dict[str, object]:
    return run_check()


def test_no_new_shim_gaps(contract_report: dict[str, object]) -> None:
    """Observed gaps must be a subset of the recorded allowlist."""

    gaps: list[str] = contract_report["gaps"]  # type: ignore[assignment]
    regressions = sorted(set(gaps) - load_allowlist())
    assert not regressions, (
        f"{len(regressions)} new `_compat` shim gap(s) "
        f"(targeted={contract_report['shims_targeted']}, "
        f"clean={contract_report['clean']}):\n  " + "\n  ".join(regressions)
    )


def test_report_allowlist_drift(contract_report: dict[str, object]) -> None:
    """Surface allowlist entries that are now satisfied — the remediation delta."""

    gaps: set[str] = set(contract_report["gaps"])  # type: ignore[arg-type]
    closed = sorted(load_allowlist() - gaps)
    assert not closed, (
        f"{len(closed)} shim gap(s) are closed but still listed in "
        "known_shim_gaps.txt. Delete these lines and record the delta in the PR "
        "description:\n  " + "\n  ".join(closed)
    )


def test_every_shim_module_is_reachable(contract_report: dict[str, object]) -> None:
    """A shim import target that names no module at all is a hard extraction bug.

    Distinguished from an incomplete shim because there is nothing to complete —
    the caller must be rerouted or the module created.
    """

    gaps: list[str] = contract_report["gaps"]  # type: ignore[assignment]
    unimportable = sorted(g for g in gaps if ":: unimportable ::" in g)
    allowed = {g for g in load_allowlist() if ":: unimportable ::" in g}
    regressions = sorted(set(unimportable) - allowed)
    assert not regressions, "new unimportable shim target(s):\n  " + "\n  ".join(regressions)
