# Independent Validation Receipts

Production does not trust caller-supplied validator headers such as `X-Validated-By-Agent`, `X-Independent-Validator-ID`, or `X-Validation-Stage`.

Independent validation evidence is represented by `IndependentValidationReceipt` in `governance/validation_receipts.py`. The receipt binds:

| Field | Purpose |
|---|---|
| `tenant_id` | Prevents cross-tenant reuse. |
| `message_id` and `message_hash` | Prevents replay for a different message. |
| `originating_agent_id` and `validator_agent_id` | Enforces validator separation. |
| `validator_role` | Requires an authorized validator role. |
| `policy_hash` and `constitutional_hash` | Binds evidence to policy and constitution versions. |
| `issued_at` and `expires_at` | Limits replay window. |
| `signature` | HMAC signature required in production. |

The verifier rejects tenant mismatch, message hash mismatch, same-agent validation, unauthorized validator role, expired receipts, unsigned production receipts, signature mismatch, and replayed receipt IDs.
