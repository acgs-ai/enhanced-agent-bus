# Critical Path Tests

The critical-path suite lives under `tests/critical_path/`.

Run:

```bash
python -m pytest tests/critical_path -q --import-mode=importlib
```

Coverage added:

| File | Guarantee |
|---|---|
| `test_message_lifecycle.py` | Async submit returns `accepted_for_processing`; valid/invalid messages resolve to approved/rejected; sync mode returns immediate rejection; spoofed validator headers are rejected in prod; tenant-bound status lookup rejects cross-tenant access. |
| `test_independent_validation_receipts.py` | Unsigned prod receipts, expired receipts, replayed receipts, same-originator validation, and tenant mismatch are rejected; valid signed receipts are accepted. |
| `test_runtime_profile.py` | Prod disallows governance fallback and fails on missing auth, unavailable Redis, and mock policy backend. |
| `test_route_authz.py` | Production mutating message route rejects unauthenticated fallback auth. |
| `test_audit_receipts.py` | Decision receipts are created for approvals/rejections and audit-chain tampering is detected. |
