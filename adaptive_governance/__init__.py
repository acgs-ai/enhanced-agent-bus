"""
ACGS-2 Adaptive Governance System
Constitutional Hash: cdd01ef066bc6cf2

Implements ML-based adaptive governance with dynamic impact scoring and
self-evolving constitutional thresholds for intelligent AI safety governance.

This package provides:
- Data models and enums for governance (models.py)
- Adaptive threshold management (threshold_manager.py)
- ML-based impact assessment (impact_scorer.py)
- Core governance engine (governance_engine.py)

Public API functions and classes are re-exported from this module to maintain
backward compatibility with the original single-file structure.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any, TypeAlias

from .amendment_recommender import (
    AmendmentRecommendation,
    AmendmentRecommender,
    RecommendationPriority,
    RecommendationTrigger,
)
from .impact_scorer import ImpactScorer
from .models import (
    GovernanceDecision,
    GovernanceMetrics,
    GovernanceMode,
    ImpactFeatures,
    ImpactLevel,
)
from .threshold_manager import AdaptiveThresholds
from .trace_collector import TraceCollector, TrajectoryRecord

if TYPE_CHECKING:
    from .dtmc_learner import DTMCFitResult, DTMCLearner
    from .governance_engine import AdaptiveGovernanceEngine

MessagePayload: TypeAlias = dict[str, Any]
PolicyContext: TypeAlias = dict[str, Any]

# Constitutional imports
from ..exceptions.operations import GovernanceError

# Global instance
_adaptive_governance: Any | None = None

_LAZY_EXPORT_MODULES = {
    "AB_TESTING_AVAILABLE": ".governance_engine",
    "DRIFT_MONITORING_AVAILABLE": ".governance_engine",
    "ONLINE_LEARNING_AVAILABLE": ".governance_engine",
    "AdaptiveGovernanceEngine": ".governance_engine",
    "DTMCFitResult": ".dtmc_learner",
    "DTMCLearner": ".dtmc_learner",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORT_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(_LAZY_EXPORT_MODULES[name], __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


async def initialize_adaptive_governance(constitutional_hash: str) -> AdaptiveGovernanceEngine:
    """Initialize the global adaptive governance engine."""
    global _adaptive_governance

    if _adaptive_governance is None:
        from .governance_engine import AdaptiveGovernanceEngine

        _adaptive_governance = AdaptiveGovernanceEngine(constitutional_hash)
        await _adaptive_governance.initialize()

    return _adaptive_governance


def get_adaptive_governance() -> AdaptiveGovernanceEngine | None:
    """Get the global adaptive governance engine instance."""
    return _adaptive_governance


async def evaluate_message_governance(
    message: MessagePayload, context: PolicyContext
) -> GovernanceDecision:
    """Evaluate a message using adaptive governance."""
    governance = get_adaptive_governance()
    if governance is None:
        raise GovernanceError("Adaptive governance not initialized")

    return await governance.evaluate_governance_decision(message, context)


def provide_governance_feedback(
    decision: GovernanceDecision, outcome_success: bool, human_override: bool | None = None
) -> None:
    """Provide feedback to improve governance models."""
    governance = get_adaptive_governance()
    if governance:
        governance.provide_feedback(decision, outcome_success, human_override)


# Export key classes and functions
__all__ = [
    "AB_TESTING_AVAILABLE",
    # Availability flags
    "DRIFT_MONITORING_AVAILABLE",
    "ONLINE_LEARNING_AVAILABLE",
    "AdaptiveGovernanceEngine",
    "AdaptiveThresholds",
    # Amendment recommender
    "AmendmentRecommendation",
    "AmendmentRecommender",
    # DTMC trajectory scorer
    "DTMCFitResult",
    "DTMCLearner",
    "GovernanceDecision",
    "GovernanceMetrics",
    "GovernanceMode",
    "ImpactFeatures",
    "ImpactLevel",
    "ImpactScorer",
    "RecommendationPriority",
    "RecommendationTrigger",
    "TraceCollector",
    "TrajectoryRecord",
    "evaluate_message_governance",
    "get_adaptive_governance",
    "initialize_adaptive_governance",
    "provide_governance_feedback",
]
