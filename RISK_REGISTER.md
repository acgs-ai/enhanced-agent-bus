# Risk Register

| Risk | Severity | Current Status | Mitigation | Test Coverage | Owner |
|---|---:|---|---|---|---|
| Production starts with missing auth secret | High | Mitigated | `require_auth_secret()` in startup checks | `tests/critical_path/test_runtime_profile.py` | Runtime |
| Redis unavailable in prod | High | Mitigated | Startup `ping()` fails closed | `tests/critical_path/test_runtime_profile.py` | Runtime |
| Mock policy backend in prod | High | Mitigated | Prod rejects mock policy URL | `tests/critical_path/test_runtime_profile.py` | Runtime |
| Spoofed validator metadata | High | Mitigated | Prod rejects validator headers; receipt verifier added | `tests/critical_path/test_message_lifecycle.py` | Security |
| Unsigned independent validation receipt | High | Mitigated | Prod verifier rejects unsigned receipts | `tests/critical_path/test_independent_validation_receipts.py` | Governance |
| Replayed validation receipt | High | Mitigated | Receipt ID replay tracking | `tests/critical_path/test_independent_validation_receipts.py` | Governance |
| Cross-tenant message status access | High | Mitigated | Tenant-bound status lookup | `tests/critical_path/test_message_lifecycle.py` | API |
| Audit receipt tampering | High | Mitigated | Chained receipt hashes | `tests/critical_path/test_audit_receipts.py` | Audit |
| Durable production message status persistence missing | Medium | Open | Add Postgres/Redis status repository | Not covered yet | Persistence |
| Full route role matrix not regression-tested | Medium | Open | Add route authz tests for every mutating route | Partial existing tests | Security |
