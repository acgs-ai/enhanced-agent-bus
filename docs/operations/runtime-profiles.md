# Runtime Profiles

Set `EAB_PROFILE` explicitly.

| Profile | Allowed | Not Allowed |
|---|---|---|
| `dev` | In-memory fallback, mock policy client, relaxed local testing behavior, non-durable state | Production claims |
| `demo` | Controlled fallback behavior and deterministic examples | Silent auth bypass, silent in-memory governance state, compliance-grade claims |
| `prod` | Authenticated tenant-aware operation with external state and health checks | In-memory governance fallback, mock policy backend, unsigned validation receipts, missing auth secrets |

All fallback decisions should route through `api/runtime_profile.py`:

- `is_dev()`
- `is_demo()`
- `is_prod()`
- `require_prod_dependency(name, condition)`
- `allow_fallback(feature_name)`
