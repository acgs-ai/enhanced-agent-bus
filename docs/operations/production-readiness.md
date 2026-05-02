# Production Readiness

Production startup uses `EAB_PROFILE=prod` and fails closed when critical dependencies are unavailable.

Required checks:

| Dependency | Check |
|---|---|
| Auth secret | One of `ACGS2_SERVICE_SECRET`, `JWT_SECRET`, `JWT_SECRET_KEY`, or `EAB_AUTH_SECRET` must be set. |
| Redis governance state | `await redis.ping()` must succeed. |
| PostgreSQL workflow state | Repository initialization plus `SELECT 1` must succeed. |
| Policy backend | Configured backend must not be mock and health must be healthy/ready/ok. |
| Audit backend | Configured audit backend health must be healthy. |

Development and demo profiles may use controlled fallbacks. Production must use durable external dependencies for governance-critical state.
