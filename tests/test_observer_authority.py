"""Observer projection and immutable MCP read-authority regressions."""

import pytest

from enhanced_agent_bus._compat.constants import MACIRole
from enhanced_agent_bus.maci_role_projection import project_to_mcp_tool_role
from enhanced_agent_bus.mcp.maci_filter import (
    MACIToolFilter,
    MACIToolRole,
    ToolFilterConfig,
)

READS = ["audit_query_logs", "policy_list_all", "policy_get_current"]
DENIED = ["audit_verify_entry", "policy_validate_v1", "compliance_check",
          "audit_write_entry", "policy_apply_v1", "tenant_provision_new", "policy_propose_v1"]


@pytest.mark.parametrize("role", [MACIRole.MONITOR, "MONITOR", "monitor", "observer"])
def test_observer_ceiling_survives_proposer_environment_override(monkeypatch, role):
    monkeypatch.setenv("MACI_FILTER_PROPOSER_PATTERNS", "*")
    flt = MACIToolFilter()
    assert flt.check_access("proposer", "policy_propose_v1")
    assert flt.allowed_patterns(role) == ["audit_query_*", "policy_list_*", "policy_get_*"]
    assert flt.filter_tools(role, READS + DENIED) == READS
    for tool in READS + DENIED:
        result = flt.check_access_detailed(role, tool)
        assert result.permitted == (tool in READS)
        assert flt.check_access(role, tool) == result.permitted
        assert result.to_audit_dict()["role"] == "observer"


def test_custom_observer_patterns_cannot_widen_authority():
    config = ToolFilterConfig(role_tool_matrix={MACIToolRole.OBSERVER: ["*"]})
    flt = MACIToolFilter(config)
    assert config.resolved_matrix()[MACIToolRole.OBSERVER] == flt.allowed_patterns("observer")
    assert flt.filter_tools(MACIToolRole.OBSERVER, READS + DENIED) == []
    exported = flt.allowed_patterns("observer")
    exported.append("*")
    assert not flt.check_access("observer", "policy_apply_v1")


@pytest.mark.parametrize("matrix", [{}, {MACIToolRole.OBSERVER: []}])
def test_custom_empty_observer_authority_denies_all(matrix):
    flt = MACIToolFilter(ToolFilterConfig(role_tool_matrix=matrix))
    assert flt.allowed_patterns("observer") == []
    assert flt.filter_tools("monitor", READS + DENIED) == []


def test_custom_observer_authority_can_narrow_but_not_widen():
    flt = MACIToolFilter(ToolFilterConfig(role_tool_matrix={
        MACIToolRole.OBSERVER: ["policy_get_specific", "*", "policy_*", "audit_write_*"],
    }))
    assert flt.allowed_patterns("observer") == ["policy_get_specific"]
    assert flt.filter_tools("observer", ["policy_get_specific"] + READS + DENIED) == [
        "policy_get_specific",
    ]


@pytest.mark.parametrize("role, expected", [
    (MACIRole.EXECUTIVE, "proposer"), (MACIRole.LEGISLATIVE, "proposer"),
    (MACIRole.MONITOR, "observer"), (MACIRole.JUDICIAL, "validator"),
    (MACIRole.AUDITOR, "validator"), (MACIRole.CONTROLLER, "executor"),
    (MACIRole.IMPLEMENTER, "executor"),
])
def test_canonical_projections(role, expected):
    assert project_to_mcp_tool_role(role) == expected
    assert project_to_mcp_tool_role(role.value) == expected


@pytest.mark.parametrize("role, allowed, denied", [
    ("proposer", "policy_get_v1", "policy_apply_v1"),
    ("validator", "policy_validate_v1", "policy_apply_v1"),
    ("executor", "policy_apply_v1", "policy_validate_v1"),
])
def test_legacy_role_defaults(role, allowed, denied):
    flt = MACIToolFilter(ToolFilterConfig())
    assert flt.check_access(role, allowed)
    assert not flt.check_access(role, denied)


def test_unknown_remains_denied():
    flt = MACIToolFilter(ToolFilterConfig(strict_mode=False))
    assert not flt.check_access("unknown", "policy_get_v1")
    assert flt.allowed_patterns("unknown") == []
