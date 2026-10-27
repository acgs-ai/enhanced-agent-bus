# MCP role authority

Canonical roles are projected by `maci_role_projection.py` into this subsystem's
tool filter roles. The projection is a local authorization policy, not identity
equivalence across repositories.

| Canonical role | Tool role | Default tool patterns |
| --- | --- | --- |
| EXECUTIVE, LEGISLATIVE | proposer | audit_query_*, policy_list_*, policy_get_* |
| JUDICIAL, AUDITOR | validator | audit_verify_*, policy_validate_*, compliance_* |
| CONTROLLER, IMPLEMENTER | executor | audit_write_*, policy_apply_*, tenant_provision_* |
| MONITOR | observer | audit_query_*, policy_list_*, policy_get_* (maximum authority) |

Previously MONITOR inherited the proposer policy, which was read-only by default
but could be expanded through environment or programmatic configuration. MONITOR
now has independent observer authority. Custom observer patterns can narrow
access: only patterns beginning with the literal prefixes `audit_query_`,
`policy_list_`, or `policy_get_` are retained. Other patterns, including `*`,
are discarded. A custom matrix with no observer entry or an empty observer
list denies all observer calls. For example, `policy_get_specific` grants only
that tool; it does not implicitly grant the rest of the default read patterns.
There is no observer environment override. Allowed-pattern inspection, bulk
filtering and detailed access decisions use the same effective matrix. Unknown
roles remain denied. AUDITOR intentionally retains verification-tool authority
via validator; it is not an alias for the read-only observer.

These are tool-name permissions. They depend on correctly classified read tools;
they do not prove that an implementation matching a read prefix has no side effects.
Canonical MONITOR action permissions independently remain QUERY and
MONITOR_ACTIVITY. A caller must still authenticate the role; passing a string to
the filter is not authentication.

## Separate scope contracts

Agent YAML permissions describe agent configuration. Per-invocation authorization
scopes constrain an individual request. APCC tuple scopes describe capability
constraints in the APCC contract. None is automatically interchangeable with this
tool-name allowlist or with each other: adapters must explicitly validate their
own schema and enforce the applicable constraints. This change introduces no
shared scope schema and no implicit delegation between these contracts.

Regression coverage: `tests/test_observer_authority.py` and
`tests/test_maci_role_matrix.py`. Neo4j is not required for enforcement or tests.
