"""
ACGS-2 CCAI Democratic Framework - Governance Package
Constitutional Hash: 608508a9bd224290

This package provides the CCAI (Collective Constitutional AI) democratic governance
framework for constitutional AI governance with democratic deliberation.

Re-exports all public APIs from submodules for backward compatibility.

Modules:
    - models: Data models (Enums, dataclasses)
    - polis_engine: Polis-style deliberation engine
    - democratic_governance: Democratic constitutional governance framework

Constitutional Hash: 608508a9bd224290
"""

from importlib import import_module
from typing import Any

from .capability_passport import (
    CapabilityDomain,
    CapabilityPassport,
    DomainAutonomy,
    PassportRegistry,
    get_passport_registry,
    infer_domain,
    reset_passport_registry,
)
from .danger_signal import (
    AdaptiveQuorumDecision,
    AdaptiveQuorumMode,
    DangerSeverity,
    DangerSignal,
    DangerSignalAnalyzer,
)
from .governance_proposal import GovernanceProposal, ProposalStatus
from .loop_orchestrator import GovernanceLoopOrchestrator, get_orchestrator, reset_orchestrator
from .models import (
    CONSTITUTIONAL_HASH,
    ConstitutionalProposal,
    DeliberationPhase,
    DeliberationResult,
    DeliberationStatement,
    OpinionCluster,
    Stakeholder,
    StakeholderGroup,
)

_LAZY_EXPORTS = {
    "DemocraticConstitutionalGovernance": (
        "democratic_governance",
        "DemocraticConstitutionalGovernance",
    ),
    "ccai_governance": ("democratic_governance", "ccai_governance"),
    "deliberate_on_proposal": ("democratic_governance", "deliberate_on_proposal"),
    "get_ccai_governance": ("democratic_governance", "get_ccai_governance"),
    "PolisDeliberationEngine": ("polis_engine", "PolisDeliberationEngine"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "CapabilityDomain",
    "CapabilityPassport",
    "DomainAutonomy",
    "DangerSeverity",
    "DangerSignal",
    "DangerSignalAnalyzer",
    "AdaptiveQuorumMode",
    "AdaptiveQuorumDecision",
    "PassportRegistry",
    "get_passport_registry",
    "infer_domain",
    "CONSTITUTIONAL_HASH",
    "ConstitutionalProposal",
    "DeliberationPhase",
    "DeliberationResult",
    "DeliberationStatement",
    "DemocraticConstitutionalGovernance",
    "GovernanceLoopOrchestrator",
    "GovernanceProposal",
    "OpinionCluster",
    "PolisDeliberationEngine",
    "ProposalStatus",
    "Stakeholder",
    "StakeholderGroup",
    "ccai_governance",
    "deliberate_on_proposal",
    "get_ccai_governance",
    "get_orchestrator",
    "reset_orchestrator",
    "reset_passport_registry",
]
