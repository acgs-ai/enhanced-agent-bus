# Threat Model

| Threat | Required Mitigation | Current Status |
|---|---|---|
| Spoofed validator metadata | Signed or server-side validation receipts | Production message route rejects spoofable validator headers; receipt verifier added. |
| Cross-tenant data access | Tenant-bound auth and storage keys | Message status and receipt stores are tenant-bound. |
| Replayed validation receipt | Message hash, expiry, receipt ID replay tracking | Receipt verifier checks hash, expiry, and replay. |
| Policy backend unavailable | Fail closed in production | Startup policy backend health check added. |
| Redis unavailable | Fail closed in production | Startup Redis ping added for governance state. |
| Audit tampering | Chained hash receipts | Governance decision receipt chain verification added. |
| Weak dev defaults in production | Runtime profile enforcement | `EAB_PROFILE=prod` disallows fallbacks. |
| Unauthenticated policy mutation | Admin authorization | Matrix documents required posture; existing policy route still needs full role test expansion. |
| Downgrade to mock governance | Production profile prohibition | Mock/fallback helpers route through `api/runtime_profile.py`. |
| Stale constitutional hash | Receipt policy/hash binding | Validation and decision receipts bind constitutional hash. |
