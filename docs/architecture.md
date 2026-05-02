# Architecture

`enhanced-agent-bus` is organized around four runtime planes.

| Plane | Responsibility | Current primary modules |
|---|---|---|
| API plane | HTTP routing, auth dependencies, tenant extraction, request/response contracts | `api/app.py`, `api/routes/*`, `api/dependencies.py` |
| Governance plane | MACI checks, constitutional hash validation, independent validation receipts, governance decision receipts | `maci_enforcement.py`, `governance_core.py`, `governance/validation_receipts.py`, `governance/decision_receipts.py` |
| Execution plane | Background/synchronous message processing and workflow execution | `message_processor/`, `persistence/executor.py` |
| Persistence plane | Redis-backed governance state, PostgreSQL workflow state, audit/receipt stores | `api/app.py`, `persistence/postgres_repository.py`, `audit_client.py` |

Message ingestion is intentionally separate from governance approval. `POST /api/v1/messages` records `accepted_for_processing`; processing then advances the status to `governance_pending`, `governance_approved`, `governance_rejected`, or `failed`.

Production profile startup is a governance boundary. It must fail when authentication secrets, Redis governance state, workflow persistence, policy backend health, or audit backend health are unavailable.
