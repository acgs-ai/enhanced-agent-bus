# Changelog draft: 3.1.0

Draft for review. It is written to `docs/` because `CHANGELOG.md` carries the
`Constitutional Hash` marker and is outside this task's allowed paths. Merge into
`CHANGELOG.md` by hand when releasing.

**Provenance and gaps.** This clone is shallow: `git rev-list --count HEAD` is 4 and the
oldest commit is `e4ecaf5` (2026-07-29, merge of PR #11). There is no `v3.0.2` tag, so
`git log v3.0.2..HEAD` is not possible. The last release was 2026-04-05; everything merged
between 2026-04-05 and 2026-07-29 is invisible here, and `CHANGELOG.md` itself stops at
2.5.0 (no 3.0.x entries). Complete this draft from a full-history clone before release.
The `e4ecaf5` entry below is based on its merge subject plus the dependency comments now in
`pyproject.toml`; its individual commits were not inspected.

## [3.1.0] - unreleased

### Added

- **`eab` command line** (`cli.py`, `[project.scripts] eab`).
  - `eab version` prints the installed package version.
  - `eab check <message.json | ->` validates a `MessageRequest` (the API's request model),
    builds the message with the API's own `_build_agent_message`, runs it through
    `MessageProcessor.process` (the call behind `POST /api/v1/messages`) offline, prints a
    JSON report, and exits `0` allow, `1` deny, `2` could not validate. Input the API would
    reject, non-finite numbers, duplicate keys and input over 2 MiB exit `2`. It runs with
    `isolated_mode=True`; the decision is `ALLOW_ISOLATED` / `DENY_ISOLATED` and the report
    lists the effective verdict-affecting flags and the skipped gates (authentication, tenant
    binding, MACI, OPA, Rust and composite strategies, session governance, ...). It is not a
    production governance approval.
- **`acgs` extra**: `pip install "enhanced-agent-bus[acgs]"` installs `acgs-lite>=4,<5`.
- **`LICENSE`**: the Apache-2.0 text (identical to the canonical apache.org text), matching
  the declared `license = {text = "Apache-2.0"}`.
- README quickstart: install, `eab check` example, running the API server.
- MACI: `MONITOR` is projected to an independent observer role with a read-only prefix
  ceiling and deny-all narrowing (`7024b2f`).

### Changed

- Package version 3.0.2 to 3.1.0 in `pyproject.toml` and `__init__.py` (`__version__`), with the
  two test assertions updated.
- Dependencies declared in `pyproject.toml` (`uvicorn`, `structlog`, `email-validator`,
  `cryptography`, `sqlalchemy`), the wheel no longer ships the test tree, and both are held
  by conformance ratchets (PR #11, `e4ecaf5`).
- `_compat/constants.py` and `_compat/types` expose concrete static exports while keeping
  the runtime compatibility imports (`7024b2f`).

### Fixed

- `tests/test_governance_core.py` no longer fails collection when `acgs-lite` is not
  installed; it is skipped via `pytest.importorskip("acgs_lite")`.
- The import-boundary scan now sees string-literal dynamic imports (`import_module("x")`,
  `importlib.import_module("x")`, `__import__("x")`). It surfaces one known, optional
  violation, `governance_core.py: constitutional_swarm`, recorded in `KNOWN_VIOLATIONS`
  (PR #13, `4ded19b`). The module docstring that claimed swarm never imports EAB was corrected.

### Known issues carried into 3.1.0

- `tests/test_init_coverage.py` imports `packages.enhanced_agent_bus` and fails entirely
  (270 tests) outside the monorepo layout; its `3.1.0` assertion cannot run here.
- Without numpy, `MessageProcessor` raises inside its SDPC verifier stubs
  (`'_NoOpIntentClassifier' object has no attribute 'classify_async'`) and exhausts retries,
  so no message can be allowed (and with numpy, `PACARVerifier.verify()` rejects the
  `session_id` keyword, so messages with a high `impact_score` also cannot be validated).
  `eab check` reports this as "cannot validate" (exit 2).
- `ValidationResult.decision` defaults to `"ALLOW"` even when `is_valid` is `False`.
  `eab check` requires both to agree.
- A plain `pip install` serves HTTP 400 `SECURITY_FALLBACK_REJECTED` for every request,
  because the shared `src.core.shared.security` package is not installed (set
  `ENVIRONMENT=development` for local use only).
- `llm_adapters/tests/test_constrained_output.py` imports `acgs_lite.constitution` unguarded
  at module level (it has a module-level skip mark, but the import runs first).
