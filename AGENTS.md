# AGENTS.md - Enhanced Agent Bus

Scope: `packages/enhanced_agent_bus/`.

This package is the ACGS governance runtime: FastAPI API surface, message bus,
MACI enforcement, constitutional workflows, deliberation, persistence, MCP
integration, observability, and optional extension shims.

## Working Rules

- Keep changes small, behavior-preserving, and directly tied to the task.
- Do not revert unrelated dirty worktree state.
- Use `rg` for search and targeted tests before broader suites.
- Add or run regression coverage before cleanup/refactor edits.
- Do not edit generated artifacts, caches, coverage output, build output, or local state.
- Do not commit secrets, local `.env` files, machine paths, MLflow runs, or OMC/OMX runtime state.
- Prefer existing package patterns over new abstractions or dependencies.

## Namespace Contracts

| Namespace | Contract |
| --- | --- |
| `middlewares/` | Canonical middleware stack. Put new middleware here. |
| `middleware/` | Deleted. Never import `enhanced_agent_bus.middleware`. |
| `context_memory/` | Canonical context/memory subsystem. Prefer for new code. |
| `context/` | Legacy compatibility shim. Avoid for new code. |
| `persistence/` | Workflow/runtime persistence. Keep isolated from saga persistence. |
| `saga_persistence/` | Saga state persistence. Keep isolated from `persistence/`. |

JWT algorithm parsing must go through
`enhanced_agent_bus._compat.security.jwt_algorithms.resolve_jwt_algorithm`.
Do not add module-local JWT allowlists unless the narrower posture is documented
next to the code and in operator-facing docs.

## Runtime Posture

- Fail closed on auth, policy, MACI, OPA, tenant isolation, and governance decisions.
- SDPC PACAR (`message_requires_pacar`: TASK_REQUEST or impact > 0.8) is enforcing: when
  PACAR ran, anything but `sdpc_pacar_valid is True` rejects in `verification_coordinator.py`
  before handlers run. Missing/unknown verdicts, verifier exceptions and the no-op stub
  (SDPC deps missing) all deny. PACAR-routed messages bypass the validation cache, and
  PACAR session history is keyed per tenant. `impact_score` is caller-supplied, so only
  TASK_REQUEST routing is unconditional. The default `_DefaultAssistant` is a stub that
  always approves; wire a real assistant before relying on PACAR as a control.
- Optional dependency shims (`_ext_*.py`, `_compat/`) must keep imports stable and
  provide explicit typed fallbacks.
- Preserve public imports and wire contracts; this package has compatibility shims
  used by tests and downstream packages.
- Use `structlog` or the existing package logging helper in runtime code.
- Do not use `eval()` or `exec()`.

## Where To Look

| Task | Paths |
| --- | --- |
| FastAPI app/routes | `api/`, `routes/` |
| Bus routing/orchestration | `agent_bus.py`, `bus/`, `message_processor.py`, `message_processor/` |
| Governance and validation | `constitutional/`, `governance/`, `maci/`, `validators.py`, `policy_client.py` |
| Deliberation/HITL | `deliberation_layer/` |
| Context and memory | `context_memory/`, legacy `context/` |
| Workflow state | `persistence/`, `saga_persistence/` |
| MCP | `mcp/`, `mcp_server/`, `mcp_integration/` |
| Observability/performance | `observability/`, `optimization_toolkit/`, `_ext_*.py` |
| Optional Rust kernels | `rust/` |

## Verification

From the package directory:

```bash
python -m ruff check <changed-python-files>
python -m py_compile <changed-python-files>
python -m pytest <targeted-tests> -q --import-mode=importlib
git diff --check
```

For type-related changes, run mypy from the parent packages directory to avoid
duplicate module-name resolution:

```bash
cd /home/martin/Downloads/ACGS/packages
MYPY_CACHE_DIR=/tmp/eab_mypy_cache python -m mypy -m enhanced_agent_bus.<module> \
  --config-file enhanced_agent_bus/mypy.ini
```

Full package tests are expensive; prefer focused tests unless touching shared
exports, app startup, middleware, or cross-cutting runtime contracts.

## Local Agent Automation

Package-local Claude Code assets live under `.claude/`:

- `skills/eab-focused-verify/` - focused verification workflow.
- `skills/eab-stop-gate-review/` - immediately previous turn review workflow.
- `agents/eab-security-governance-reviewer.md` - security/governance diff reviewer.
- `hooks/` - edit guards for deleted middleware imports, JWT parsing, artifacts,
  and focused Python verification.

Keep these files concise. Put long rationale in `docs/`, not auto-loaded guidance.

## Subdirectory Guidance

Read a subdirectory `AGENTS.md` only when editing inside that subtree. Keep
subdirectory guides limited to local behavior that differs from this file.
