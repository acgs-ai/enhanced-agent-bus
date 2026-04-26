# FINAL PRODUCT PRD — ACGS

> Handoff-ready product direction and PRD for the ACGS repository.
> Target audience: engineering, product leadership, and investor-facing stakeholders.
> Date: 2026-04-24. Based on state of repo at commit `6a696e0`.

---

## 0. Evidence Basis and Source Caveats

This document is grounded **only** in the repository at `/home/martin/Downloads/ACGS/` as of 2026-04-24. Web research was **not** performed; competitive claims are drawn from context in `README.md`, `docs/`, and package `pyproject.toml` files. Claims that cannot be verified from the repo are explicitly marked *(assumption)* or *(unverified)*.

Key evidence files cited below:
- `/home/martin/Downloads/ACGS/README.md` — monorepo pitch
- `/home/martin/Downloads/ACGS/packages/acgs-lite/README.md` — embeddable SDK
- `/home/martin/Downloads/ACGS/packages/enhanced_agent_bus/README.md` — FastAPI service
- `/home/martin/Downloads/ACGS/packages/clinicalguard/README.md` — healthcare A2A agent
- `/home/martin/Downloads/ACGS/packages/constitutional_swarm/README.md` — multi-agent runtime
- `/home/martin/Downloads/ACGS/packages/enhanced_agent_bus/prd.json` — US-001..US-008 remediation stories
- `/home/martin/Downloads/ACGS/workers/governance-proxy/` — edge proxy
- `/home/martin/Downloads/ACGS/rust/` — PyO3 hot-path engine
- `/home/martin/Downloads/ACGS/hackathon-demo/` — Auth0 demo

---

## 1. Diagnosis — What This Project Is Right Now

### 1.1 Observable product surface

| Artifact | License | Location | Real product? |
|---|---|---|---|
| `acgs-lite` v2.10.0 | Apache-2.0 | `packages/acgs-lite/` | **Yes** — PyPI, 5,623 tests, CLI + SDK, 11 integrations |
| `enhanced-agent-bus` v3.0.2 | Apache-2.0 | `packages/enhanced_agent_bus/` | **Yes** — PyPI, FastAPI service, 14 routers, ~751 test files |
| `acgs-deliberation` v0.1.1 | Apache-2.0 | split from bus | Partial — extracted surface, early |
| `clinicalguard` v1.0.1 | **AGPL-3.0** | `packages/clinicalguard/` | Reference implementation, Starlette A2A JSON-RPC |
| `legalguard` v1.0.0 | **AGPL-3.0** | `packages/legalguard/` (assumed) | Reference implementation |
| `constitutional-swarm` v1.0.0 | **AGPL-3.0** | `packages/constitutional_swarm/` | Research-adjacent, multi-agent |
| Cloudflare Worker | n/a | `workers/governance-proxy/` | Internal infra, not hosted SaaS |
| Rust/PyO3 engine | Apache-2.0 | `rust/` | Optional acceleration, Python fallback parity |
| SvelteKit frontend | Apache-2.0 | `packages/acgs.ai/`, `packages/acgs-dashboard/` | Unverified; likely WIP dashboards |

### 1.2 What problem is actually solved

The README frames the problem as *"a single mother denied a mortgage in 340ms with no appeal."* That is **regulatory/compliance language**, not developer tooling language. The actual code delivers:

1. **Runtime policy enforcement** against a YAML-authored constitution before an agent action executes (`acgs_lite.GovernedAgent`, `acgs_lite.maci.MACIEnforcer`).
2. **Tamper-evident audit logging** (SHA-256 chain) for every decision (`acgs_lite.audit`).
3. **Compliance reports** mapping enforcement events to 9 regulatory frameworks (EU AI Act, NIST AI RMF, ISO 42001, SOC 2, HIPAA, GDPR, ECOA/FCRA, NYC LL 144, OECD AI).
4. **Runtime bus** for multi-agent systems that want centralized governance (`enhanced_agent_bus.api.app`).

All four are real and tested. The weakest link is the *glue* — there is no coherent narrative taking a prospective customer from `pip install` to a monitored production workload.

### 1.3 Likely user/customer today

Three populations, only one of which is clearly served:

| Candidate ICP | Served by today's shape? | Why |
|---|---|---|
| **Compliance/Risk officer at a regulated AI shop** | Partially | The CLI + audit reports are valuable, but the rest of the repo is noise to them. |
| **Platform engineer at an AI-first startup** | Poorly | They want an SDK and a hosted endpoint, not another FastAPI service to run. |
| **Multi-agent researcher** | Well | `constitutional-swarm`, Z3, Bittensor-ish research modules fit their world. |

The stated mission ("HTTPS for AI") suggests the compliance officer ICP is intended. The shipped artifacts over-index on the researcher ICP.

### 1.4 Strongest use case (empirical)

`pip install acgs-lite && acgs-lite eu-ai-act --domain healthcare` → 60-second compliance checklist with 65% auto-coverage and a PDF.

This single flow is:
- **Time-bound** (EU AI Act full enforcement: August 2, 2026 — ~14 weeks from 2026-04-24)
- **Financially material** (7% global revenue / €35M max penalty)
- **Self-serve** (one command, no SaaS sign-up)
- **Defensible** (72/125 controls auto-populated across 9 frameworks — replicating this is real work)

This is the wedge. Everything else is downstream.

### 1.5 Weakest / most confusing parts

| Problem | Evidence |
|---|---|
| **Too many SKUs** | 6+ PyPI packages + 2 licenses (Apache vs AGPL) + Cloudflare Worker + Rust engine. No clear "start here" for a new customer. |
| **Name sprawl** | ACGS, acgs-lite, enhanced-agent-bus, acgs-deliberation, acgs.ai, acgs-dash, acgs-forge. README uses "HTTPS for AI" but the install is `acgs-lite`. |
| **Claim/implementation gap** | "Used in regulated pilots" *(unverified)*. No customer logos, no case studies in the repo. |
| **"Constitutional hash `608508a9bd224290`"** | Marketed as a governance primitive; operationally it is a SHA-256 tamper-detection value. Useful but oversold. |
| **Two persistence layers** | `persistence/` vs `saga_persistence/` in `enhanced_agent_bus`. CLAUDE.md keeps them separate intentionally; ADR rationale is not customer-visible. |
| **Heavy optional deps in one package** | `enhanced_agent_bus[ml]` pulls numpy/scikit-learn/mlflow/evidently/river/pandas/onnxruntime/tokenizers. Even if gated, the *perception* is bloat. |
| **493 pytest skip marks** | Most are environment-gated (Redis/OPA/LLM), which is correct, but the ratio looks alarming to an auditor. |
| **Circular-import footgun in `api/app.py`** | `message_processor` must import before `persistence.executor` (autoresearch regression ~1500ms if reordered). Documented, but fragile. |

### 1.6 Production-ready vs. research/prototype

| Subsystem | State |
|---|---|
| YAML constitution + Aho-Corasick validator | **Production** |
| MACI role enforcement | **Production** |
| SHA-256 audit chain | **Production** |
| Compliance report generator | **Production** |
| CLI (`acgs-lite eu-ai-act`, `acgs-lite init`) | **Production** |
| Rate limiting, circuit breakers, health probes | **Production** |
| Durable workflows (`persistence.executor`) | **Production** — PostgreSQL + in-memory fallback |
| Enterprise SSO (LDAP/SAML/OIDC) | **Production (unverified in customer use)** |
| Deliberation / HITL voting | **Beta** — 28 files, fewer integration tests |
| Adaptive governance / `ImpactScorer` (DistilBERT → int8 ONNX after recent autoresearch) | **Beta** |
| Z3 SMT formal verification | **Beta** — optional, mostly research framing |
| Post-quantum crypto (`_ext_pqc`) | **Experimental** — optional `[pqc]` extra |
| `constitutional-swarm` Bittensor integration | **Research** |
| SvelteKit dashboards (`packages/acgs.ai/`, `acgs-dashboard/`) | **Unverified / WIP** |
| Cloudflare Worker as public product | **Not productized** |

---

## 2. Research — Market Positioning

> No live web research. Adjacent-tool names below are paraphrased from repo-internal mentions and common-knowledge context; pricing, traction, and feature comparisons are *assumptions* unless otherwise noted.

### 2.1 Nearby categories

| Category | Example tools | Where ACGS fits |
|---|---|---|
| LLM output guardrails | Llama Guard 2, Guardrails AI, NeMo Guardrails, Promptfoo | ACGS enforces before execution, not just on output. Stronger audit trail. |
| Policy-as-code | Open Policy Agent (OPA), Cedar | ACGS *uses* OPA optionally (`opa_client/`); doesn't compete head-on. |
| Agent frameworks | LangChain, CrewAI, AutoGen, LiteLLM | ACGS is explicitly integration-only — 11 integrations listed — not a competitor. |
| AI compliance platforms | Credo AI, Holistic AI, CalypsoAI, Lakera | Likely closest commercial competitors. *(assumption)* ACGS differentiates with open-source core + runtime enforcement. |
| Multi-agent governance research | Anthropic constitutional AI, ICML/FAccT submissions | ACGS has a paper trail (`docs/PAPER-TO-CODE.md`) but this is not a commercial moat. |

### 2.2 Strongest positioning claim defensible today

**"The open-source runtime that makes EU AI Act compliance testable, automatable, and auditable — before your agents ship."**

This is defensible because:
1. Runtime enforcement + tamper-evident audit + 9-framework mapping is a genuinely rare combination in open source.
2. The EU AI Act deadline creates compelled buying behavior in high-risk categories (healthcare, HR, credit).
3. Apache-2.0 on the core (`acgs-lite`) lowers procurement friction vs. fully AGPL alternatives.
4. Existing domain reference implementations (`clinicalguard`, `legalguard`) shorten time-to-pilot in the two most lucrative regulated verticals.

### 2.3 Positioning claims that should be retired

| Retire | Replace with |
|---|---|
| "HTTPS for AI" | "Runtime compliance for AI agents." HTTPS framing is too grand and sets up a metaphor ACGS can't deliver (no certificate authority, no protocol standardization). |
| "Constitutional hash" as governance primitive | Call it what it is: a **build integrity hash** / **policy version fingerprint**. |
| "Sub-5ms P99" headline | Keep the number in benchmarks, not marketing. The variance is hardware-dependent and the Python-only path isn't that fast. |
| "Used in regulated pilots" | Either publish 1–2 named customer case studies (even pseudonymized) or drop the claim. |

---

## 3. Recommended Product Direction

### 3.1 The call

**Build this first: a single commercial product called "ACGS Compliance Runtime" that wraps `acgs-lite` as its SDK and ships an auditor-facing compliance console + managed edge proxy for regulated AI workloads in the EU.**

Everything else becomes either (a) an open-source on-ramp funneling to the commercial product, or (b) deprecated.

### 3.2 What stays, what changes, what goes

| Asset | Decision | Rationale |
|---|---|---|
| `acgs-lite` (SDK + CLI) | **KEEP — product core** | This is the wedge. Remains open-source Apache-2.0 forever. |
| Compliance report generator | **KEEP — commercial surface** | This is what auditors and CFOs pay for. Promote into dedicated package. |
| `enhanced-agent-bus` | **KEEP — advanced tier** | Retain as "self-hosted runtime" for customers that need multi-tenant. De-emphasize in homepage copy. |
| Cloudflare Worker (`workers/governance-proxy/`) | **PROMOTE — hosted product** | Productize as "ACGS Cloud" — managed governance at the edge. Billing hook required. |
| `clinicalguard`, `legalguard` | **RENAME — reference implementations** | Reposition as "ACGS Reference Agents." Keep AGPL; lets enterprises fork safely or buy a commercial license. |
| `constitutional-swarm` | **SPIN OFF or ARCHIVE** | Bittensor/peer-validation is a distinct research story. Either make it an explicit research repo, or archive to reduce cognitive load. |
| Rust/PyO3 engine | **KEEP INTERNAL** | Acceleration detail, not a product. Stop mentioning P50/P99 in pitch. |
| `acgs.ai` + `acgs-dashboard` SvelteKit | **CONSOLIDATE** | Pick one. The other ships as internal-only. |
| `acgs-deliberation` | **MERGE BACK** | Either promote to a real package or reabsorb into `enhanced-agent-bus`. Half-split is confusing. |
| `mhc` alias package | **RENAME or DELETE** | Short-import alias adds name sprawl. Delete unless an external consumer depends on it (requires `pip grep` against known downstream). |
| `propriety-ai`, `acgs-forge` | **DELETE from public surface** | WIP code shouldn't be in `packages/` if it isn't shipped. |

### 3.3 Why this is stronger than alternatives

| Alternative direction | Why weaker |
|---|---|
| **Multi-agent trust infrastructure** (lead with `constitutional-swarm`) | Demand signal is thin. Multi-agent is a research vertical, not a buying motion. Buyer ≠ signer. |
| **Framework-neutral policy engine** (compete with OPA/Cedar) | Commoditized market, slow buying cycles, needs integrations into dozens of agent frameworks. |
| **Horizontal AI safety platform** (compete with Lakera/Credo) | Requires a sales motion ACGS doesn't have yet and a ML threat model that's only partially built. |
| **"HTTPS for AI" protocol standard** | Protocol plays take 5+ years and require consortium formation. Not a startup motion. |
| **Stay as-is (multi-SKU open-source playground)** | Current state. No revenue path, diluted positioning, high maintenance tax. |

### 3.4 Core product promise (the one line)

**"Your AI agents stay compliant before they act — not after an incident."**

### 3.5 Ideal customer profile (initial)

- **Vertical:** Healthcare (CDS, prior auth, clinical research triage) OR HR/financial services (hiring, credit, underwriting) — both are EU AI Act "high risk" systems.
- **Size:** Series B through mid-market, 50–2,000 employees, already deploying LLM-driven workflows in production.
- **Geography:** EU-regulated or EU-serving, or US-regulated (HIPAA, ECOA).
- **Buyer:** Head of AI / Chief AI Officer (technical buyer), Chief Risk/Compliance Officer (economic buyer).
- **Pain trigger:** External deadline (EU AI Act Aug 2026, internal audit finding, regulator inquiry, model incident).

### 3.6 Wedge use case

**"Generate a signed EU AI Act Article 9–15 coverage report for my healthcare AI system in 60 seconds, then plumb the same rules into my agent runtime so violations are blocked before they execute."**

This is a single-command experience today. Productizing it is mostly polish, packaging, and a managed delivery path — not greenfield engineering.

---

## 4. FINAL PRODUCT PRD — "ACGS Compliance Runtime"

### A. Executive Summary

ACGS Compliance Runtime is a runtime governance layer for AI agents that blocks non-compliant actions before execution and emits tamper-evident audit trails mapped to 9 regulatory frameworks. The commercial product consists of three tiers: an open-source embeddable SDK (`acgs-lite`), a self-hosted multi-tenant runtime (`enhanced-agent-bus`), and a managed edge service (ACGS Cloud, built on Cloudflare Workers). The wedge is EU AI Act compliance automation, time-bound by August 2026 full enforcement. Core engineering is stable (≥5,600 tests, Apache-2.0). The 30/60/90-day plan focuses on packaging, trust artifacts, and the managed-service GA.

### B. Product Vision

Every AI decision made in a regulated environment is emitted against a cryptographically-versioned policy, checked before execution, and logged to a tamper-evident trail the auditor can query without engineering help. ACGS becomes the default way regulated enterprises deploy agentic AI.

### C. Problem Statement

Regulated organizations must deploy AI agents faster than their compliance teams can hand-audit. The EU AI Act, HIPAA, ECOA, NIST AI RMF, ISO 42001, and SOC 2 each demand evidence of policy enforcement at runtime — not post-hoc explanations. Existing guardrail libraries filter *outputs*, while policy-as-code tools (OPA, Cedar) don't understand agent intent. The gap is an agent-aware runtime that enforces policies *before* action and produces audit-grade records.

### D. Target Users / ICP

Primary — Chief Risk / Chief Compliance Officer at EU-regulated enterprises deploying LLM agents in high-risk categories (healthcare, HR, credit, education). Buyer.

Secondary — Head of AI / Staff Platform Engineer at AI-native SaaS companies with enterprise customers who are themselves EU-regulated. Implementer / technical champion.

Tertiary (later) — Research labs and academic groups studying multi-agent governance, via `constitutional-swarm`.

### E. Core Use Cases

1. **Generate EU AI Act compliance report** — CLI-driven, 60 seconds, PDF + JSON. Owner: Compliance.
2. **Embed constitution in agent runtime** — 5-line Python integration, fail-closed enforcement. Owner: Platform engineering.
3. **Query audit trail for incident forensics** — Hash-chained log, exportable to SIEM. Owner: Security / Compliance.
4. **Pilot governed multi-agent workflow** — Multi-tenant bus with MACI role separation (Proposer/Validator/Executor/Observer). Owner: Platform engineering.
5. **Managed edge governance** — Point OpenAI-compatible traffic at ACGS Cloud, get governance + audit without running any infra. Owner: Buyer of managed service.

### F. Product Positioning

**For** regulated enterprises deploying AI agents
**who** must prove runtime policy enforcement to regulators and auditors,
**ACGS** is a runtime compliance engine
**that** blocks non-compliant actions before they execute and emits tamper-evident audit trails mapped to 9 frameworks.
**Unlike** output-filtering guardrails (Guardrails AI, Llama Guard) or policy-as-code tools (OPA, Cedar),
**our product** is agent-aware, fail-closed by default, and ships with auditor-ready compliance reports for EU AI Act, NIST AI RMF, and HIPAA out of the box.

### G. Competitive Differentiation

| Differentiator | Evidence in repo |
|---|---|
| **Agent-aware MACI enforcement** | `enhanced_agent_bus/maci/` — roles prevent self-validation at runtime |
| **9-framework compliance mapping** | `acgs-lite` CLI; 72/125 checklist items auto-populated |
| **Tamper-evident audit chain** | SHA-256 chain in `acgs_lite.audit`; chain verification implemented |
| **Open-source core** | Apache-2.0 on `acgs-lite` and `enhanced-agent-bus` — lowers procurement friction |
| **Domain reference implementations** | `clinicalguard` (healthcare, 20 rules) and `legalguard` (legal) — shortcuts to pilot |
| **Sub-ms validation hot path** | `rust/validator.rs` PyO3, with verified Python fallback parity |

### H. MVP Scope (90 days)

| Item | File/Package | Status today | MVP action |
|---|---|---|---|
| Consolidated brand + install path | repo root + `packages/acgs-lite/` | Fragmented | Collapse to `acgs-lite` as the only install command in README |
| EU AI Act report polish (one-command → PDF + JSON + CSV) | `acgs-lite` CLI | 60-sec prototype | Add signing, QR verify, 3 case-study fixtures |
| Audit chain export (SIEM JSON, CSV, Parquet) | `acgs_lite.audit` | JSON only | Add CSV + Parquet, time-range filters |
| Managed edge governance (ACGS Cloud) | `workers/governance-proxy/` | Internal worker | Add Stripe metering, tenant isolation, admin console |
| Single SvelteKit dashboard | `packages/acgs.ai/` OR `acgs-dashboard/` | Two dashboards, unclear owner | Pick one, delete or internalize the other |
| Trust kit (SOC 2 Type 1 letter, pen test, 1 case study) | n/a | Missing | External — see ticket T-017 |
| Docs consolidation | `docs/` + many READMEs | Sprawled | Single `/docs` site with role-based entry points (Compliance / Platform Eng / Researcher) |

### I. Non-MVP / Later Scope

- `constitutional-swarm` research pack (spin-off or archive decision at end of MVP)
- Post-quantum crypto (`_ext_pqc`) — stays optional, no marketing push
- Bittensor subnet integration — research-only
- Additional language SDKs (TypeScript/Go) — post-PMF
- On-prem air-gapped deployment bundle — reactive to first enterprise ask

### J. Core User Flows

**Flow 1 — Compliance officer self-serve**
1. `pip install acgs-lite`
2. `acgs-lite init`
3. `acgs-lite eu-ai-act --domain healthcare --system-id prod-scoring`
4. Review PDF, hand to counsel.
5. (Upsell) `acgs-lite enforce --stream` for runtime violations dashboard.

**Flow 2 — Platform engineer integration**
1. `from acgs_lite import Constitution, GovernedAgent`
2. Wrap existing LangChain/CrewAI/custom agent.
3. Add 1 env var pointing at audit export.
4. Deploy. Every action logged + policy-checked.

**Flow 3 — ACGS Cloud (hosted)**
1. Sign up at `acgs.ai` (SvelteKit frontend).
2. Upload or author constitution in console.
3. Switch agent base URL to `https://cloud.acgs.ai/v1/`.
4. Read audit log + compliance posture in console.

**Flow 4 — Multi-tenant self-hosted**
1. `docker run enhanced-agent-bus` with Redis + Postgres.
2. Register tenants via `/api/v1/tenants`.
3. Route agents through `POST /` with constitutional headers.
4. Monitor via Prometheus + `/health/*`.

### K. Functional Requirements

- **FR-1** Policy definition in YAML with typed rule DSL. Must support include/override layering.
- **FR-2** Pre-execution validation of proposed agent actions against the active policy version.
- **FR-3** MACI role enforcement: no agent validates its own output. Enforced at runtime, not advisory.
- **FR-4** Tamper-evident audit log: SHA-256 chain, per-entry signature, verifiable offline.
- **FR-5** Compliance report generation for 9 named frameworks (EU AI Act, NIST AI RMF, ISO 42001, SOC 2, HIPAA, GDPR, ECOA/FCRA, NYC LL 144, OECD AI).
- **FR-6** Fail-closed behavior on all governance decision paths (auth, policy, MACI, OPA, governance, tenant).
- **FR-7** Hot-swappable constitutions with version tracking and diff audit.
- **FR-8** OpenAI-compatible HTTP proxy for `/v1/chat/completions` and `/v1/embeddings` (ACGS Cloud tier).
- **FR-9** Multi-tenant isolation: constitution, audit store, rate limit, MACI registry per tenant.
- **FR-10** Human-in-the-loop deliberation workflow: proposal → multi-approver vote → consensus → execute/reject.
- **FR-11** Export audit to S3-compatible storage, Kafka, and local file.
- **FR-12** Stripe-metered billing hook (ACGS Cloud tier): events / GB-audit / seats.

### L. Non-Functional Requirements

- **NFR-1** Hot-path validation: Python-only P99 ≤ 10 ms; Rust path P99 ≤ 2 ms on commodity AMD64 (documented, not guaranteed).
- **NFR-2** Availability: self-hosted tier MUST support Kubernetes liveness/readiness/startup probes (already implemented in `enhanced_agent_bus/api/routes/health.py`).
- **NFR-3** Cold-start: `enhanced_agent_bus.api.app` import ≤ 2.5 s on reference hardware (post-autoresearch baseline, 2026-04-24).
- **NFR-4** Security: fail-closed everywhere, no `str(exc)` in URL/credential handlers, all inputs Pydantic-validated.
- **NFR-5** Supply chain: every release signed + SBOM emitted, constitutional hash recorded per release.
- **NFR-6** Offline operability: compliance report generation and audit verification MUST work air-gapped.
- **NFR-7** Data residency: ACGS Cloud tier MUST offer EU-only processing (Cloudflare EU edges) by design.

### M. Technical Architecture

Three tiers, one SDK surface:

```
┌────────────────────────────────────────────────────────────┐
│ Tier 3 — ACGS Cloud (managed)                              │
│   workers/governance-proxy (Cloudflare Workers, D1, KV)    │
│   + SvelteKit console (packages/acgs.ai)                   │
└────────────────┬───────────────────────────────────────────┘
                 │ uses same policy + audit primitives
┌────────────────▼───────────────────────────────────────────┐
│ Tier 2 — Self-hosted Runtime (advanced)                    │
│   enhanced-agent-bus (FastAPI, Redis, Postgres, Kafka)     │
│   Multi-tenant, durable workflows, deliberation, SSO       │
└────────────────┬───────────────────────────────────────────┘
                 │ embeds
┌────────────────▼───────────────────────────────────────────┐
│ Tier 1 — SDK Core (open source, Apache-2.0)                │
│   acgs-lite (Python SDK + CLI)                             │
│   Constitution, GovernedAgent, MACIEnforcer, AuditLog      │
│   Optional: rust/ PyO3 hot path                            │
└────────────────────────────────────────────────────────────┘
```

Cross-cutting:
- Policy + audit primitives live in `acgs-lite` (and optionally accelerated via `rust/`).
- Tier 2 and Tier 3 *use* tier 1; they don't reimplement validation.
- Domain agents (`clinicalguard`, `legalguard`) are reference implementations sitting on tier 2, sold either as AGPL open-source or commercial license.

### N. Data Model / Config Model

**Constitution (YAML)**
```yaml
id: healthcare-v1
hash: 608508a9bd224290  # build-integrity fingerprint
domain: healthcare
frameworks: [eu_ai_act, hipaa, nist_ai_rmf]
rules:
  - id: no-dosage-outside-range
    severity: block
    pattern: ...
    rationale: ...
```

**Audit entry**
```json
{
  "prev_hash": "…",
  "entry_hash": "…",
  "ts": "2026-04-24T12:34:56Z",
  "tenant_id": "t_abc",
  "constitution_hash": "608508a9bd224290",
  "agent_id": "agent_xyz",
  "role": "Executor",
  "action": {...},
  "decision": "allow|deny|require_hitl",
  "matched_rules": ["no-dosage-outside-range"],
  "signature": "…"
}
```

**Tenant config (service mode)**
```json
{
  "tenant_id": "t_abc",
  "constitution_id": "healthcare-v1",
  "rate_limit_rpm": 120,
  "maci_roles": {"proposer": [...], "validator": [...], ...},
  "audit_sink": {"type": "s3", "bucket": "...", "kms_key": "..."}
}
```

### O. CLI / API / UI Requirements

**CLI (`acgs-lite`)**
- `acgs-lite init` — scaffold rules + CI
- `acgs-lite eu-ai-act --domain <d> --system-id <id>` — compliance report
- `acgs-lite assess --framework <f>` — alternate framework
- `acgs-lite audit verify <path>` — verify chain offline
- `acgs-lite audit export --format <csv|jsonl|parquet> --since <ts>` — SIEM export
- `acgs-lite serve` — run local debug server (thin wrapper around Tier 2)

**HTTP API (`enhanced-agent-bus` + `ACGS Cloud`)**
- Keep the 14 existing routers (health, messages, batch, policies, governance, public_v1, badge, signup, stats, usage, widget_js, workflows, z3, agent_health).
- Add `/v1/chat/completions`, `/v1/embeddings` (OpenAI-compatible proxy) on Tier 3.
- Add `/api/v1/tenants/*`, `/api/v1/admin/constitutions/*` for management.
- Add `/metrics` (Prometheus) — already partially present via `observability/`.

**UI (SvelteKit console)**
- Compliance posture dashboard (per-framework score, last assessment, drift).
- Audit search + export.
- Constitution editor + diff viewer.
- HITL deliberation queue.
- Billing + usage (Tier 3).

### P. Security, Compliance, and Audit Requirements

- Fail-closed on auth, policy, MACI, OPA, tenant, governance — enforced by CI lint rules (`.claude/rules/security.md`).
- No `str(exc)` in URL/credential handlers — enforced by test + review.
- `ACGS2_SERVICE_SECRET` only via env (set by `conftest.py` in tests) — never hard-coded.
- Rate limiting on all public endpoints (slowapi).
- JWT issuer/audience validation on inter-service calls.
- Constitutional hash recorded on every response for tamper detection.
- Release pipeline signs wheels (Sigstore/cosign) and emits SBOM (CycloneDX).
- ACGS Cloud tier SOC 2 Type 1 within 90 days; Type 2 within 12 months *(commercial commitment)*.

### Q. Observability Requirements

- Structured logs (`structlog`) with correlation IDs in all paths.
- Prometheus metrics: request rate, latency histograms, policy-decision counters, MACI-role mix, circuit breaker state, deliberation queue depth.
- Alerts: fail-closed decision count per tenant (anomaly-worthy), audit sink backlog, circuit breaker tripped.
- Trace export (OTel) — add if not present; verify via `observability/` files.
- Every audit log export records time-to-export and integrity check result.

### R. Developer Experience Requirements

- Time-to-first-governed-agent (TTFGA): ≤ 5 minutes from `pip install` on a fresh machine.
- `acgs-lite init` scaffolds a working policy + CI workflow.
- Cookbook (`docs/cookbook/`): LangChain, CrewAI, LangGraph, AutoGen, LiteLLM, Anthropic SDK, OpenAI SDK. *(Some integrations listed in README — verify each one has runnable code under `examples/`.)*
- Error messages must cite rule ID, matched text, and remediation.
- All public APIs typed; mypy strict on core.

### S. Integration Requirements

- 11 integrations claimed in README: Anthropic, MCP, GitLab CI/CD, OpenAI, LangChain, LiteLLM, Google GenAI, LlamaIndex, AutoGen, CrewAI, A2A.
- For each, MUST have: (a) runnable example, (b) end-to-end test, (c) docs page. Audit this list — any that don't have all three fall back to "experimental" badge on the docs page.
- Auth0 Token Vault integration (`hackathon-demo/`) graduates to a first-class "OAuth governance" example.
- OPA integration (`opa_client/`): document the contract explicitly.

### T. Acceptance Criteria (MVP / 90-day)

- [ ] Single documented install path (`pip install acgs-lite`) with ≤ 5-line quickstart.
- [ ] `acgs-lite eu-ai-act` command returns signed PDF + JSON + CSV for all 9 frameworks.
- [ ] Audit chain verification CLI passes chain-of-trust test suite.
- [ ] ACGS Cloud closed beta with ≥ 3 paying pilots (even at $0, with LOIs).
- [ ] SOC 2 Type 1 letter or 1 published case study (whichever ships first).
- [ ] Homepage copy replaces "HTTPS for AI" with "runtime compliance for AI agents."
- [ ] Single SvelteKit console (one of `acgs.ai`/`acgs-dashboard` shipped, other deleted).
- [ ] `constitutional-swarm` either spun off or clearly marked "research — not part of commercial product."
- [ ] CI enforces: constitutional hash unchanged per release, fail-closed lint rules, SBOM emission.
- [ ] `enhanced_agent_bus` cold-start remains ≤ 2.5 s (guardrail test gated in CI).

### U. Risks and Open Questions

| Risk | Impact | Mitigation |
|---|---|---|
| **EU AI Act interpretation shifts before Aug 2026** | High | Version constitutions; publish a compatibility matrix; subscribe customers to update channel. |
| **Crowded market (Credo/Holistic/Lakera)** | Medium | Lean into runtime enforcement + audit trail + open-source — genuinely rare combination. |
| **AGPL on domain packages scares enterprises** | Medium | Offer commercial licenses; keep `acgs-lite` Apache-2.0 as the on-ramp. |
| **`enhanced-agent-bus` surface area too large to maintain** | Medium | Split less-used subsystems (Z3, bittensor, PQC) into clearly labeled optional extras; consider archiving. |
| **"Circular-import guard" fragility** | Low | Documented; guarded by eval script; still a footgun — consider refactoring `persistence/__init__.py` post-MVP. |
| **Performance claims don't match customer hardware** | Medium | Stop leading with P99 numbers; publish a reproducible bench kit. |
| **Trust artifacts missing (no case studies, no third-party attestation)** | High | External; assign to founder/CEO. Without one of {SOC 2 Type 1, named customer, third-party pen test}, enterprise sales stall. |

**Open questions**
1. Is there actually an EU entity signing a pilot? Required for "regulated pilots" claim to stay.
2. Does `acgs-dashboard` or `acgs.ai` win the UI consolidation? Need a UX audit.
3. Should `constitutional-swarm` be spun off to its own org? Or archived? Or kept as a research showcase driving inbound?
4. Which integration pairs (LangChain+Anthropic? CrewAI+OpenAI?) are the *real* top 2 we double-down on?
5. Does the business model center on ACGS Cloud (usage) or enterprise self-host (seat-based license)? Early pricing experiments needed.
6. Is the Auth0 Token Vault demo a signal of an Auth0 partnership lane? Confirm with founder.

### V. 30 / 60 / 90 Day Roadmap

**Days 0–30 — Narrative and Trust**
- Consolidate homepage copy + single install path (T-001, T-002).
- Pick winning SvelteKit surface; archive the other (T-003).
- Ship EU AI Act report hardening: signing, QR verify, case-study fixtures (T-004).
- Audit chain export — CSV + Parquet (T-005).
- Archive or clearly label `constitutional-swarm`, `propriety-ai`, `acgs-forge` (T-006).
- Publish 1 named or pseudonymized customer case study, *or* kick off SOC 2 Type 1 (T-017; external).

**Days 31–60 — Managed Service Beta**
- ACGS Cloud closed beta: tenant isolation, Stripe metering, admin console (T-007, T-008, T-009).
- Replace "HTTPS for AI" framing in all surfaces (T-010).
- Audit the 11 framework integrations; graduate/demote each (T-011).
- Refactor dual `persistence/` vs `saga_persistence/` documentation into a single explainer (T-012).
- `cold-start ≤ 2.5s` CI guardrail on `enhanced_agent_bus.api.app` (T-013).

**Days 61–90 — Commercial GA**
- ACGS Cloud GA: pricing page, terms, data residency (EU-only option) (T-014).
- 3 paying pilots live (commercial).
- SOC 2 Type 1 letter (stretch) OR named case study published (must).
- Public benchmark kit (reproducible) replacing marketing P99 numbers (T-015).
- Consolidated `/docs` information architecture shipped (T-016).

### W. Engineering Task Breakdown

See next section.

### X. Investor-Facing Product Narrative

**Why now.** The EU AI Act takes full enforcement on August 2, 2026, with penalties up to 7% of global revenue. Every regulated enterprise deploying AI is buying *something* this year. Gartner-style framing suggests a $1–5 B governance/compliance tooling opportunity by 2028 *(assumption; not researched here)*. ACGS already has the stable open-source core and the single CLI command that produces an auditor-ready compliance report. The commercial wedge is converting that CLI workload into a managed service plus enterprise self-host, tied to regulatory deadlines.

**What we sell.** ACGS Cloud — managed runtime compliance for AI agents at the edge, priced per governed request and per GB of tamper-evident audit retention. ACGS Enterprise — self-hosted Kubernetes-ready multi-tenant runtime with enterprise SSO, durable workflows, HITL deliberation, and commercial support, priced per seat + tenant.

**Why we win.** (1) Runtime enforcement, not output filtering. (2) Audit trail auditors can actually verify. (3) Apache-2.0 on-ramp removes procurement friction. (4) Two shipped domain reference implementations (healthcare, legal) shorten pilot cycles. (5) Explicit paper-to-code lineage gives regulatory conversations credibility. *(assumption)*

**Moat building.** (a) Customer policy libraries become switching cost. (b) Audit chain compatibility with specific SIEMs becomes a compliance prerequisite. (c) Framework coverage breadth (9 frameworks → 15 in 18 months) is a slow-copy-to-build competitive barrier. (d) Cloudflare edge deployment gives data residency + latency properties few pure-cloud competitors can match.

**Ask.** 12-month runway for 6-person engineering + 2 GTM + security/compliance program, targeting $500k ARR from 10 paying enterprise pilots and 25 ACGS Cloud commercial accounts by month 12.

---

## 5. Engineering Task Breakdown

> All tickets scoped for Codex / Claude Code execution. Priority: P0 = ship in 30 days, P1 = 60 days, P2 = 90 days. Paths shown as `packages/<pkg>/...` are relative to `/home/martin/Downloads/ACGS/`.

### T-001 — Consolidate install narrative to `acgs-lite` — **P0**
**Goal.** New user hits one install command and reaches a governed agent in ≤ 5 minutes.
**Files.** `README.md`, `docs/README.md`, `packages/acgs-lite/README.md`, `packages/enhanced_agent_bus/README.md`.
**Steps.**
1. Replace homepage install with `pip install acgs-lite`.
2. Move `enhanced-agent-bus` install into a "Self-hosted runtime" section.
3. Remove duplicate "5 lines to governed AI" variants across packages.
4. Add role-based jump-links (Compliance / Platform Eng / Researcher).
**Acceptance.** One, and only one, install path on homepage. README ≤ 300 lines.
**Tests.** Docs link-check CI job passes; every example code block runs in `make docs-test`.

### T-002 — Retire "HTTPS for AI" framing — **P0**
**Goal.** Remove a claim we cannot deliver; replace with an operational one.
**Files.** `README.md`, `packages/*/README.md`, `docs/`, `packages/acgs.ai/` landing pages.
**Steps.** Global search and replace "HTTPS for AI" → "runtime compliance for AI agents" in marketing-surface files; leave internal/ADR references intact.
**Acceptance.** Zero occurrences in customer-facing files; one explanatory ADR under `docs/decisions/`.
**Tests.** Docs lint rule flags the phrase in customer-facing files.

### T-003 — Pick one SvelteKit surface and archive the other — **P0**
**Goal.** One console, one repo path, one deploy.
**Files.** `packages/acgs.ai/`, `packages/acgs-dashboard/`, `Makefile`, CI.
**Steps.** UX audit (1 day). Pick winner. Move complementary pages in. Archive loser with a pointer.
**Acceptance.** Single frontend package. One "npm run dev" path.
**Tests.** Frontend CI green; Playwright/Vitest suite passes on winner.

### T-004 — EU AI Act report: signing, QR verify, case-study fixtures — **P0**
**Goal.** Make the 60-second report actually auditor-accepted.
**Files.** `packages/acgs-lite/src/acgs_lite/cli/eu_ai_act.py` (or equivalent), `packages/acgs-lite/templates/`.
**Steps.** Add Ed25519 signature on the generated PDF metadata. Embed a QR code pointing to an online verifier. Add 3 fixture system profiles (healthcare, credit, HR).
**Acceptance.** `acgs-lite eu-ai-act` emits signed PDF + JSON + CSV. Verifier round-trips on all 3 fixtures.
**Tests.** Golden-file tests for PDF structure; signature verify test.

### T-005 — Audit export: CSV + Parquet + time-range filters — **P0**
**Goal.** SIEM/warehouse compatibility out of the box.
**Files.** `packages/acgs-lite/src/acgs_lite/audit/`, `packages/acgs-lite/src/acgs_lite/cli/audit.py`.
**Steps.** Add `to_csv`, `to_parquet` exporters. Add `--since`, `--until`, `--tenant` filters. Integrity check on export.
**Acceptance.** 100k-entry audit log exports in ≤ 2 s on reference hardware.
**Tests.** Round-trip JSON → Parquet → JSON equality; chain-integrity preserved after export.

### T-006 — Archive/spin-off non-core packages — **P0**
**Goal.** Reduce surface area; clarify what is "the product."
**Files.** `packages/constitutional_swarm/` (archive or spin-off decision), `packages/propriety-ai/`, `packages/acgs-forge/`, `packages/mhc/`, `packages/acgs-deliberation/`.
**Steps.** For each, decide: keep / mark research / reabsorb / delete. Update `docs/repo-map.md`. If spun off, add a one-line note + link in root README.
**Acceptance.** `packages/` contains only what the commercial product depends on, or what is explicitly labeled "reference implementation" or "research."
**Tests.** `repo-map.md` links are all live; no dangling imports.

### T-007 — ACGS Cloud tenant isolation — **P1**
**Goal.** Managed service can onboard multiple customers safely.
**Files.** `workers/governance-proxy/src/`, Worker KV schema, D1 schema.
**Steps.** Per-tenant constitution namespace in KV. Per-tenant audit stream in D1 (encrypted at rest with tenant-derived key). Tenant-scoped rate limits. JWT with `tenant_id` claim required on all `/v1/*` calls.
**Acceptance.** Cross-tenant access attempt returns 403 with audit entry. Fuzz test (100 random tenant IDs) shows zero leakage.
**Tests.** Integration: spin up 2 tenants, verify isolation on constitution, audit, and rate limit.

### T-008 — ACGS Cloud Stripe metering hook — **P1**
**Goal.** We can charge for it.
**Files.** `workers/governance-proxy/src/billing.ts` (new), admin console.
**Steps.** Integrate Stripe Metered Billing API. Emit usage records for: (governed requests, GB-audit retained, seats). Reconcile daily.
**Acceptance.** Test-mode invoice generated after 1,000 synthetic requests matches expected line items within ±0.1%.
**Tests.** Mock Stripe server; property tests on metering arithmetic.

### T-009 — ACGS Cloud admin console MVP — **P1**
**Goal.** Customer self-serve for constitution, audit, billing.
**Files.** chosen SvelteKit package (`packages/acgs.ai/` likely).
**Steps.** Pages: Constitutions (list/edit/deploy), Audit (search/export), Billing (usage/invoices), Team (invite/roles). Auth via Auth0 or Clerk (decide by day 45).
**Acceptance.** Customer can create a constitution, deploy it, route 1 request, and see the audit entry within 3 clicks.
**Tests.** Playwright E2E happy path; unit tests on SvelteKit stores.

### T-010 — Brand + positioning sweep — **P1**
**Goal.** One coherent story across repo, PyPI, docs, social.
**Files.** All READMEs, `docs/`, `packages/acgs.ai/` content.
**Steps.** Ship content guide in `docs/brand.md` (tone, allowed claims, banned claims). Review and rewrite every package README top-card to match.
**Acceptance.** Editorial review passes on all 8+ READMEs.
**Tests.** Docs lint (banned-phrase list) green.

### T-011 — Integration matrix audit — **P1**
**Goal.** Every listed integration is real or demoted.
**Files.** `packages/acgs-lite/examples/`, `docs/integrations/`.
**Steps.** For each of 11 integrations: verify (a) runnable example, (b) e2e test, (c) docs page. Missing any → demote badge to "experimental" and open follow-up ticket.
**Acceptance.** Every production-badged integration has all three artifacts.
**Tests.** CI matrix runs each example on every PR.

### T-012 — Docs merge: `persistence/` vs `saga_persistence/` ADR — **P1**
**Goal.** Stop confusing new engineers; make the boundary a feature, not a footgun.
**Files.** `packages/enhanced_agent_bus/docs/adr/adr-0003-persistence-split.md` (new), `packages/enhanced_agent_bus/AGENTS.md`, `CLAUDE.md`.
**Steps.** Write the ADR. Reference from both package dirs. Add a one-paragraph section to the package README.
**Acceptance.** New engineer reading the ADR can answer: why two modules, what goes where, what not to cross-import.
**Tests.** Docs lint: ADR is linked from the relevant code paths via `README` or module docstrings.

### T-013 — Cold-start CI guardrail on `enhanced_agent_bus.api.app` — **P1**
**Goal.** Don't regress the autoresearch wins silently.
**Files.** `.github/workflows/perf.yml` (new), `packages/enhanced_agent_bus/eval_api_app_startup.py` (exists).
**Steps.** Run `eval_api_app_startup.py` on every PR. Fail if median > 2,800 ms (20% margin above 2,300 ms ceiling).
**Acceptance.** PRs that reorder `message_processor`/`persistence` imports fail CI.
**Tests.** Synthetic regression PR (reorder imports) correctly fails CI.

### T-014 — ACGS Cloud pricing page + EU residency opt-in — **P2**
**Goal.** Public GA.
**Files.** `packages/acgs.ai/routes/pricing/`, Worker routing config.
**Steps.** Pricing tiers, self-serve checkout, EU-only edge toggle (Cloudflare geo routing), terms of service, DPA template.
**Acceptance.** Customer can sign up EU-only from pricing page end-to-end.
**Tests.** Playwright checkout happy path; Cloudflare geo assertion on EU-only tenants.

### T-015 — Public, reproducible benchmark kit — **P2**
**Goal.** Replace marketing-surface P99 numbers with something a customer can run.
**Files.** `benchmarks/public/` (new), `docs/perf.md`.
**Steps.** Build a containerized benchmark (Python-only, Rust-accelerated, multi-tenant service) with canonical dataset + script. Commit results.json on each release.
**Acceptance.** External user can `docker run acgs/bench` and get a JSON report in ≤ 5 minutes.
**Tests.** CI runs the kit nightly; drift alert if regression > 10%.

### T-016 — Docs IA overhaul — **P2**
**Goal.** Three entry points (Compliance / Platform Eng / Researcher), consistent layout.
**Files.** `docs/` tree.
**Steps.** Role-based navigation. Kill duplicate "getting started" pages. Move `PAPER-TO-CODE.md` under `docs/research/`.
**Acceptance.** Usability test with 3 users from 3 personas — each completes their target task in ≤ 10 minutes.
**Tests.** Docs link-check + Lighthouse CI.

### T-017 — Trust kit: SOC 2 readiness OR named case study — **P0 (external, not engineering-led)**
**Goal.** Something a procurement team can point at.
**Files.** n/a (legal/ops).
**Steps.** Engage SOC 2 readiness vendor; OR identify 1 pilot willing to be a named reference.
**Acceptance.** Either letter of intent from SOC 2 vendor with target Type 1 date, or case study draft in review by day 30.
**Tests.** n/a.

### T-018 — Archive `_ext_pqc` as "research tier" — **P2**
**Goal.** Stop telegraphing half-finished claims.
**Files.** `packages/enhanced_agent_bus/_ext_pqc.py`, pyproject `[pqc]` extra, README.
**Steps.** Add "research tier — not for production" banner. Ensure it still installs/tests but stays off the marketing surface.
**Acceptance.** No marketing page claims "post-quantum" unless it links the research banner.
**Tests.** Existing tests pass; banner in docstrings.

### T-019 — Refactor `persistence/__init__.py` circular chain — **P2**
**Goal.** Kill the "message_processor must load first" footgun.
**Files.** `packages/enhanced_agent_bus/persistence/__init__.py`, `persistence/executor.py`, `persistence/models.py`, `data_flywheel/dataset_builder.py`.
**Steps.** Refactor so `persistence.models` is importable standalone. Remove the transitive loop through `data_flywheel`. Autoresearch eval should reproduce current ceiling without the load-bearing comment.
**Acceptance.** Direct `import enhanced_agent_bus.persistence.repository` succeeds. Cold-start eval median ≤ 2,300 ms. Remove `# ruff: noqa: I001` from `api/app.py`.
**Tests.** New unit test: isolated import of `persistence.repository`. CI guardrail (T-013) remains green.

### T-020 — Deliberation layer: docs + demo path — **P2**
**Goal.** The HITL story is real; make it narratable.
**Files.** `packages/enhanced_agent_bus/deliberation_layer/`, `examples/hitl_deliberation/` (new).
**Steps.** Runnable multi-approver example. Short video or GIF for docs. Name the voting primitive (Polis-style? Quadratic? Plain majority?) clearly.
**Acceptance.** A new engineer can demo HITL deliberation in ≤ 10 minutes.
**Tests.** E2E example runs in CI (with Redis service container).

---

## 6. Final Recommendation

**Build this first.**

**Ship T-001, T-002, T-004, T-005, T-006, T-017 in the next 30 days.**

Pick one install path. Retire "HTTPS for AI." Make the EU AI Act report auditor-grade. Ship CSV/Parquet audit export. Archive or relabel the 4 non-core packages. In parallel, close one real trust artifact (SOC 2 readiness engagement or named customer case study).

Everything else is a 60/90-day follow-on. The reason is simple: the commercial wedge is regulatory, the deadline is fixed (Aug 2, 2026), and the product engineering is already ≥ 80% done. What's missing is narrative, trust, and packaging — which are far cheaper to fix than features.

Deferring this clarification costs you two quarters of positioning ambiguity at the exact moment regulated buyers are shopping. Don't.
