# Repo Audit

## Routes

Core routers are registered in `api/app.py` through `_CORE_ROUTE_MODULES`. The highest-risk mutating surfaces are message submission, MACI governance writes, policy writes, batch submission, workflow mutation, and Z3/formal verification requests.

## Fallback Behavior

Fallbacks previously depended primarily on `ENVIRONMENT`. This change introduces `EAB_PROFILE` and centralizes fallback decisions in `api/runtime_profile.py`.

## Governance Gates

Existing gates include MACI enforcement, constitutional hash validation, OPA/policy client integration, and independent validator metadata checks. The metadata checks were spoofable when supplied by caller headers; production now rejects those headers and receipt primitives exist for verifiable evidence.

## Persistence Dependencies

Production governance state depends on Redis. Workflow state depends on PostgreSQL. Policy and audit backends are health-checked in production.

## Tests and CI

The new `tests/critical_path/` suite exercises product guarantees rather than import-only behavior. CI now runs this suite.

## Claims Requiring Care

Avoid claiming regulatory compliance by default. The accurate claim is that the runtime is designed to support auditability and provides verifiable governance decision records when deployed with production dependencies.
