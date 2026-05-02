# Overview

`enhanced-agent-bus` is a governed runtime message bus for AI agents. Its purpose is to make agent actions tenant-aware, policy-bound, role-validated, and auditable before they are routed or acted upon.

The runtime does not claim regulatory compliance by default. It provides mechanisms designed to support auditability:

- explicit runtime profiles;
- tenant-bound API access;
- MACI role separation;
- constitutional and policy hash binding;
- independent validation receipts;
- governance decision receipts;
- tamper-evident audit-chain hashes.

Production deployments must use `EAB_PROFILE=prod` with durable external dependencies.
