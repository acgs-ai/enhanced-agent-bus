# enhanced-agent-bus

[![PyPI](https://img.shields.io/pypi/v/enhanced-agent-bus)](https://pypi.org/project/enhanced-agent-bus/)
[![Python](https://img.shields.io/pypi/pyversions/enhanced-agent-bus)](https://pypi.org/project/enhanced-agent-bus/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

**ACGS-2 Enhanced Agent Bus — governed multi-tenant agent communication infrastructure designed to support constitutional policy enforcement and auditability.**

`enhanced-agent-bus` is a **FastAPI service**, not an importable library. Run it with `uvicorn`; agents and governance dashboards talk to it over HTTP. It provides agent registration, governed message routing, MACI enforcement, durable workflow execution, human-in-the-loop deliberation, Z3 formal verification, rate limiting, and Prometheus metrics.

Important production semantics:

- `202 Accepted` from `POST /api/v1/messages` means **accepted for processing**, not governance-approved.
- Use `GET /api/v1/messages/{message_id}/status` to observe `governance_pending`, `governance_approved`, or `governance_rejected`.
- `POST /api/v1/messages?mode=validate_and_route` runs the validation path synchronously and returns the immediate governance decision when the configured processor can decide it.
- Production mode requires external durable state, authentication secrets, Redis-backed governance state, policy backend health, and audit backend health.
- Development fallback behavior is not production behavior.
- Independent validation requires verifiable receipts in production; spoofable validator headers are rejected.

> **Version:** 3.0.2

## Installation and Running

```bash
pip install enhanced-agent-bus
```

Start the service:

```bash
uvicorn enhanced_agent_bus.api.app:app --host 0.0.0.0 --port 8000
```

Or with multiple workers:

```bash
uvicorn enhanced_agent_bus.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Requires Python 3.11+. Redis is required for production deployments (rate limiting, deliberation, MACI record storage).

Select the runtime profile explicitly:

```bash
export EAB_PROFILE=dev    # local development and tests
export EAB_PROFILE=demo   # controlled demos with visible fallback behavior
export EAB_PROFILE=prod   # fail-closed production profile
```

Minimal auth-related environment example:

```bash
export JWT_SECRET_KEY="replace-with-32+-char-secret"
export JWT_ALGORITHM=HS256
export JWT_ISSUER=acgs2-agent-runtime
export JWT_AUDIENCE=acgs2-services
export ACGS2_SERVICE_SECRET="replace-with-service-secret"
```

Package-level example env file:

[`packages/enhanced_agent_bus/.env.example`](.env.example)

### Docker

A production Dockerfile is included. It builds a Rust optimization kernel in a multi-stage build, then runs the service as a non-root `acgs` user:

```bash
docker build -f enhanced_agent_bus/Dockerfile -t enhanced-agent-bus .
docker run -p 8000:8000 \
  -e JWT_SECRET_KEY="replace-with-32+-char-secret" \
  -e JWT_ALGORITHM=HS256 \
  -e JWT_ISSUER=acgs2-agent-runtime \
  -e JWT_AUDIENCE=acgs2-services \
  -e ACGS2_SERVICE_SECRET="replace-with-service-secret" \
  enhanced-agent-bus
```

## API Endpoints

The service mounts 14 core routers:

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Full health report (bus, Redis, Kafka, circuit breakers) |
| `GET` | `/health/live` | Kubernetes liveness probe |
| `GET` | `/health/ready` | Kubernetes readiness probe |
| `GET` | `/health/startup` | Startup probe |
| `GET` | `/health/redis` | Redis connectivity check |
| `GET` | `/health/kafka` | Kafka connectivity check |

### Messages

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/messages` | Accept a message for governed processing (`202` is not governance approval) |
| `POST` | `/api/v1/messages?mode=validate_and_route` | Synchronously validate and return the immediate governance decision |
| `GET` | `/api/v1/messages/{message_id}/status` | Retrieve tenant-bound message lifecycle status |
| `GET` | `/api/v1/messages/{message_id}` | Compatibility status endpoint |

### Governance & MACI

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/governance/...` | MACI role query and governance state |
| `POST` | `/governance/maci/assign` | Assign a MACI role to an agent |
| `POST` | `/governance/maci/validate` | Validate an agent's action against its MACI role |
| `POST` | `/governance/maci/record` | Record a MACI governance event |
| `POST` | `/governance/maci/review` | Submit a MACI review decision |

### Agent Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/agents` | List registered agents and their health |
| `POST` | `/api/v1/agents` | Register an agent |
| `DELETE` | `/api/v1/agents/{agent_id}` | Deregister an agent |

### Policies

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/policies` | Load or update governance policies |

### Batch Processing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/batch` | Submit a batch of messages for concurrent constitutional validation |

### Workflows (durable saga execution)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workflows` | Create a durable workflow |
| `GET` | `/workflows` | List workflows |
| `GET` | `/workflows/{workflow_id}` | Inspect a workflow |
| `POST` | `/workflows/{workflow_id}/cancel` | Cancel a workflow |
| `POST` | `/workflows/{workflow_id}/retry` | Retry a failed workflow |

### Z3 Formal Verification

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/z3/...` | Z3 SMT solver status |
| `POST` | `/z3/...` | Submit a constraint for Z3 verification |

### Other endpoints

- `GET /stats` — bus statistics and Prometheus-compatible metrics
- `GET /usage` — metering and rate-limit usage
- `POST /signup` — tenant registration
- `GET /badge` — governance compliance badge generation
- `GET /widget.js` — embeddable governance widget

Optional routers (registered when dependencies are available):
- **Constitutional Review API** — structured constitutional review workflows
- **Circuit Breaker Health** — circuit breaker state and trip history
- **Session Governance API** — multi-session governance state tracking
- **Visual Studio / Copilot API** — IDE integration endpoints

## Architecture and Subsystems

### Core message bus (`agent_bus.py`)

`EnhancedAgentBus` manages agent registration, message routing, and constitutional validation. The runtime is designed so messages are traceable, tenant-bound, policy-bound, and auditable before governed action is taken. Deployment operators must use the `prod` profile and external dependencies for production-grade enforcement.

### Deliberation layer (`deliberation_layer/`)

Human-in-the-loop vote collection and consensus. Provides `DeliberationQueue`, `VotingService`, `EventDrivenVoteCollector` (Redis pub/sub), `RedisVotingSystem`, `GraphRAGContextEnricher`, and `multi_approver`. See also: the `acgs-deliberation` package, which re-exports this layer's stable surface.

### Enterprise SSO (`enterprise_sso/`)

LDAP integration, SAML/OIDC middleware, data warehouse connectors, Kafka streaming, and tenant migration tooling.

### Adaptive governance (`adaptive_governance/`)

ML-driven governance adaptation: `audit_judge`, `llm_judge`, `blue_team` red-teaming, DTMC learning, amendment recommendations, and impact scoring. `ImpactScorer` uses DistilBERT semantic scoring when `IMPACT_SCORER_MODEL_DIR` is set; falls back to keyword routing otherwise.

### Constitutional governance (`governance/`)

Democratic deliberation and domain-scoped autonomy (ADR-018):

- **`GovernanceProposal`** — State machine for ratifying suggested rules: `PENDING → DELIBERATING → CONSENSUS_REACHED → APPROVED → DEPLOYED`. Created from `SuggestedRule` via `GovernanceProposal.from_suggested_rule()`.
- **`ConstitutionDeployer`** — Deploys ratified proposals to the live constitution. Requires NMC confidence ≥ 0.67; returns the new constitutional hash on success.
- **`GovernanceLoopOrchestrator`** — Bridges `AutoSynthesizer` output → Polis deliberation → proposal lifecycle. `ingest_synthesis_report()` converts `SynthesisReport.suggestions` into proposals and submits them to Polis for community deliberation.
- **`CapabilityPassport`** (ADR-018) — Cryptographically signed per-agent capability record. Binds `agent_id` to a set of `DomainAutonomy` entries (one per `CapabilityDomain`), each specifying an autonomy tier (`ADVISORY` / `BOUNDED` / `HUMAN_APPROVED`). Signed with HMAC-SHA256 using `ACGS2_SERVICE_SECRET`. Passport verification is enforced on every tier lookup — an invalid or unsigned passport falls back to `HUMAN_APPROVED` (fail-closed).
- **`PassportRegistry`** — In-memory store for signed passports. `get_tier(agent_id, action_text)` infers domain from action text and returns the agent's tier; verifies the passport signature before trusting any domain entry.
- **`PolisDeliberationEngine`** — Polis-style deliberation: statement submission, vote collection, opinion clustering, and consensus scoring.

### MACI enforcement (`maci_enforcement.py`)

`MACIEnforcer` + `MACIRoleRegistry` — enforces PROPOSER / VALIDATOR / EXECUTOR / OBSERVER separation for every agent interaction.

### Durable workflow execution (`persistence/`)

Saga-pattern workflow executor with PostgreSQL backend (`PostgresWorkflowRepository`) and in-memory fallback (`InMemoryWorkflowRepository`).

### Batch processing (`batch_processor.py`)

`BatchMessageProcessor` — concurrent constitutional validation for bulk message ingestion with configurable item timeout, concurrency, and slow-item threshold.

### Observability

Structured logging via `observability/structured_logging.py`, Prometheus metrics via `prometheus-client`, and per-request correlation IDs.

## Configuration

Key runtime settings in `api/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_API_PORT` | `8000` | Service port |
| `DEFAULT_WORKERS` | `4` | Uvicorn worker count |
| `CIRCUIT_BREAKER_FAIL_MAX` | (configured) | Failures before circuit trips |
| `CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS` | (configured) | Circuit reset timeout |
| `BATCH_PROCESSOR_MAX_CONCURRENCY` | (configured) | Max concurrent batch items |
| `IMPACT_SCORER_MODEL_DIR` | unset | Path to DistilBERT model for semantic impact scoring; keyword fallback used when unset |
| `ACGS2_SERVICE_SECRET` | required | HMAC-SHA256 key for `CapabilityPassport` signing and verification. Must be set in any environment that registers or verifies agent passports. Tests set this via `conftest.py`; production must provide it via the environment. |

Redis connection: `REDIS_URL` environment variable (defaults to `redis://localhost:6379`).

## Security

- **Rate limiting** — 60 requests/minute per client via `slowapi` (429 on breach)
- **MACI enforcement** — every governance action checked against role permissions
- **Constitutional validation** — all messages validated before routing
- **Capability passport signing** — `CapabilityPassport` is HMAC-SHA256 signed with `ACGS2_SERVICE_SECRET`; the middleware and `PassportRegistry.get_tier()` both verify the signature before trusting any domain tier. Unverified or unsigned passports fail closed to `HUMAN_APPROVED`.
- **Non-root container** — Dockerfile creates `acgs` user (UID 1000)
- **Patched dependencies** — `pydantic>=2.12.1` (CVE-2025-6607), `litellm>=1.61.6` (CVE-2025-1499), `setuptools>=80.9.0` (CVE-2025-69226/69229), `cryptography>=44.0.2`
- **JWT authentication** — `PyJWT>=2.8.0` for bearer token validation

JWT runtime precedence and module-specific posture are documented in
[`docs/JWT_ENV_PRECEDENCE.md`](docs/JWT_ENV_PRECEDENCE.md).

Deployment note:

- tenant routes use `JWT_ALGORITHM`
- collaboration API uses `COLLABORATION_JWT_ALGORITHM` and is intentionally `HS256`-only
- session governance uses `SESSION_JWT_ALGORITHM`

## Optional Dependencies

```bash
pip install "enhanced-agent-bus[ml]"       # NumPy, scikit-learn, MLflow, Evidently, River
pip install "enhanced-agent-bus[pqc]"      # Post-Quantum Cryptography (liboqs, CRYSTALS-Kyber)
pip install "enhanced-agent-bus[postgres]" # asyncpg + SQLAlchemy for PostgreSQL persistence
pip install "enhanced-agent-bus[messaging]"# aiokafka for Kafka streaming
```

## Runtime dependencies

`fastapi`, `uvicorn`, `redis`, `httpx`, `pydantic>=2.12.1`, `litellm`, `slowapi`, `msgpack`, `pybreaker`, `prometheus-client`, `jsonschema`, `PyJWT`, `cachetools`, `PyYAML`, `psutil`, `orjson`, `aiofiles`, `python-multipart`

## License

Apache-2.0.

## Links

- [Homepage](https://acgs.ai)
- [PyPI](https://pypi.org/project/enhanced-agent-bus/)
- [Issues](https://github.com/dislovelhl/enhanced-agent-bus/issues)
- [Changelog](https://github.com/dislovelhl/enhanced-agent-bus/releases)
