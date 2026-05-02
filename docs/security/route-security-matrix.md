# Route Security Matrix

| Route | Method | Mutates State? | Requires Auth? | Requires Tenant? | Requires Role? | Production Allowed? | Notes |
|---|---|---:|---:|---:|---|---:|---|
| `/health` | `GET` | No | No | No | None | Yes | Public liveness/health surface. |
| `/health/live` | `GET` | No | No | No | None | Yes | Kubernetes liveness. |
| `/health/ready` | `GET` | No | No | No | None | Yes | Reports readiness checks. |
| `/api/v1/messages` | `POST` | Yes | Yes | Yes | Agent principal | Yes | Returns `accepted_for_processing`, not approval. |
| `/api/v1/messages/{message_id}/status` | `GET` | No | Yes | Yes | Tenant principal | Yes | Tenant-bound lookup. |
| `/governance/maci/assign` | `POST` | Yes | Yes | Yes | Admin/operator | Yes | Must remain role-gated. |
| `/governance/maci/validate` | `POST` | Yes | Yes | Yes | Validator/system | Yes | Governance-critical mutation. |
| `/governance/maci/record` | `POST` | Yes | Yes | Yes | System/admin | Yes | Audit/governance event write. |
| `/governance/maci/review` | `POST` | Yes | Yes | Yes | Validator | Yes | Human/validator review path. |
| `/policies` | `POST` | Yes | Yes | Yes | Admin/operator | Yes | Policy mutation must require elevated role. |
| `/batch` | `POST` | Yes | Yes | Yes | Agent principal | Yes | Batch governance path. |
| `/workflows` | `POST` | Yes | Yes | Yes | Agent/operator | Yes | Requires durable persistence in prod. |
| `/workflows/{workflow_id}/cancel` | `POST` | Yes | Yes | Yes | Owner/operator | Yes | Tenant ownership required. |
| `/workflows/{workflow_id}/retry` | `POST` | Yes | Yes | Yes | Owner/operator | Yes | Tenant ownership required. |
| `/z3/...` | `POST` | Yes | Yes | Yes | Validator/operator | Yes | Formal verification request. |
