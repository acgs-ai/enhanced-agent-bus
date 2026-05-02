# Risk Register

| Risk | Severity | Current Status | Mitigation | Test Coverage | Owner |
|---|---:|---|---|---|---|
| Production fallback to in-memory governance | High | Reduced | `EAB_PROFILE=prod` disallows governance fallback | `tests/critical_path/test_runtime_profile.py` | Runtime |
| Spoofed validator headers | High | Reduced | Prod route rejects spoofable validator headers; receipt verifier added | `tests/critical_path/test_message_lifecycle.py`, `test_independent_validation_receipts.py` | Security |
| Receipt replay | High | Reduced | Receipt ID replay cache, message hash, expiry | `test_independent_validation_receipts.py` | Governance |
| Cross-tenant status access | High | Reduced | Tenant-bound status store lookup | `test_message_lifecycle.py` | API |
| Audit receipt tampering | High | Reduced | Chained decision receipt hash | `test_audit_receipts.py` | Audit |
| Policy backend outage | High | Reduced | Prod startup health check | `test_runtime_profile.py` | Runtime |
| Audit backend outage | Medium | Partial | Prod startup health check added; needs deployment-specific endpoint testing | Not yet network-integrated | Runtime |
| Route authz drift | High | Partial | Security matrix added | Existing route tests plus future expansion | Security |
