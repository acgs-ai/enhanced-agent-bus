"""Ratchet: CI must actually run the conformance suite, and blocking.

The import and shim ratchets only constrain anything if a pull request runs
them. A later edit could set ``continue-on-error: true`` on that step, delete
it, or guard it with a matrix value that no leg produces — and every other test
in this directory would still pass. This test is the guard on the guard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
_JOB = "test"


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    assert WORKFLOW_PATH.is_file(), f"{WORKFLOW_PATH} is missing"
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def conformance_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the steps of the ``test`` job that invoke ``tests/conformance``."""

    steps = workflow["jobs"][_JOB]["steps"]
    return [step for step in steps if "tests/conformance" in str(step.get("run", ""))]


def test_ci_runs_the_conformance_suite(workflow: dict[str, Any]) -> None:
    """Some step must invoke tests/conformance, or the ratchets are decorative."""

    matches = conformance_steps(workflow)
    assert matches, (
        f"no step in the '{_JOB}' job of {WORKFLOW_PATH.name} runs tests/conformance. "
        "The import and _compat shim allowlists are then unenforced on pull requests."
    )


def test_the_conformance_step_is_blocking(workflow: dict[str, Any]) -> None:
    """A non-blocking ratchet reports regressions instead of preventing them."""

    soft = [
        step["name"]
        for step in conformance_steps(workflow)
        if step.get("continue-on-error") not in (None, False)
    ]
    assert not soft, (
        "conformance step(s) set continue-on-error, so a regression into "
        f"known_import_failures.txt would merge green: {soft}"
    )


def test_the_conformance_step_selects_a_real_matrix_leg(workflow: dict[str, Any]) -> None:
    """A guard naming a version the matrix does not build never runs at all."""

    job = workflow["jobs"][_JOB]
    versions = {str(v) for v in job.get("strategy", {}).get("matrix", {}).get("python-version", [])}
    for step in conformance_steps(workflow):
        guard = str(step.get("if", ""))
        if not guard:
            continue
        assert any(f"'{version}'" in guard or f'"{version}"' in guard for version in versions), (
            f"step {step.get('name')!r} is guarded by {guard!r}, which matches no "
            f"python-version in the matrix {sorted(versions)}; the step would never run"
        )
