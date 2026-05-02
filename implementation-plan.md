# Implementation Plan

## Phase 1 Completed

- Inventory routes and mutating surfaces.
- Inventory fallback behavior and governance gates.
- Identify spoofable validator metadata and accepted-vs-approved ambiguity.

## Phase 2 Completed In This Branch

- Add `api/runtime_profile.py`.
- Add production fail-closed checks for auth secret, Redis, workflow PostgreSQL, policy backend, and audit backend.
- Add explicit message lifecycle states and status endpoint.
- Reject spoofable validator headers in production.
- Add verifiable independent validation receipt primitives.

## Phase 3 Completed In This Branch

- Add structured governance decision receipt model.
- Bind receipts to tenant, message hash, policy hash, constitutional hash, timestamp, MACI roles, validator receipt IDs, and audit-chain hash.
- Add audit-chain verification tests.

## Phase 4 Completed In This Branch

- Add critical-path test suite.
- Add CI job step for `tests/critical_path`.
- Update docs and README semantics.

## Recommended Next PRs

- Replace the in-memory demo/dev status store with a durable production message status repository.
- Integrate validation receipts directly into the processor/gate coordinator path.
- Expand route authz tests for every mutating router in the matrix.
- Add OpenAPI contract tests for message lifecycle response shapes.
