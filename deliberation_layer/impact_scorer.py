"""
Impact Scorer Facade (Deliberation Layer).
Constitutional Hash: 608508a9bd224290

Provides unified impact scoring with support for:
- Basic keyword-based semantic scoring (default)
- MiniCPM-enhanced 7-dimensional governance scoring (optional)
- ONNX/TensorRT optimized inference (optional)
- Batch processing for high-throughput scenarios
"""

import hashlib
import os as _os
from typing import TYPE_CHECKING, Any, TypeAlias, cast

_IMPACT_SCORER_MODEL_DIR: str = _os.environ.get("IMPACT_SCORER_MODEL_DIR", "")

from enhanced_agent_bus.observability.structured_logging import get_logger

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = cast(Any, None)
    NUMPY_AVAILABLE = False

from enhanced_agent_bus.governance_constants import (
    IMPACT_CRITICAL_FLOOR,
    IMPACT_HIGH_SEMANTIC_FLOOR,
    IMPACT_WEIGHT_CONTEXT,
    IMPACT_WEIGHT_DRIFT,
    IMPACT_WEIGHT_PERMISSION,
    IMPACT_WEIGHT_SEMANTIC,
    IMPACT_WEIGHT_TRAJECTORY,
    IMPACT_WEIGHT_VOLUME,
)

if TYPE_CHECKING:
    from enhanced_agent_bus.adaptive_governance.dtmc_learner import DTMCLearner
else:
    DTMCLearner: TypeAlias = Any

_RuntimeDTMCLearner: Any | None
try:
    from enhanced_agent_bus.adaptive_governance.dtmc_learner import (
        DTMCLearner as _RuntimeDTMCLearner,
    )

    DTMC_AVAILABLE = True
except ImportError:
    _RuntimeDTMCLearner = None
    DTMC_AVAILABLE = False
from enhanced_agent_bus._compat.cache.manager import TieredCacheConfig, TieredCacheManager

if TYPE_CHECKING:
    from enhanced_agent_bus._compat.types import JSONDict
else:
    JSONDict: TypeAlias = dict[str, Any]

from enhanced_agent_bus.impact_scorer_infra import service as _impact_scorer_service
from enhanced_agent_bus.impact_scorer_infra.models import (
    ImpactVector,
    ScoringConfig,
    ScoringMethod,
    ScoringResult,
)

CONSTITUTIONAL_HASH = getattr(_impact_scorer_service, "CONSTITUTIONAL_HASH", "standalone")
ImpactScoringConfig = _impact_scorer_service.ImpactScoringConfig
calculate_message_impact = _impact_scorer_service.calculate_message_impact
configure_impact_scorer = _impact_scorer_service.configure_impact_scorer
cosine_similarity_fallback = _impact_scorer_service.cosine_similarity_fallback
get_gpu_decision_matrix = _impact_scorer_service.get_gpu_decision_matrix
get_impact_scorer_service = _impact_scorer_service.get_impact_scorer_service
get_profiling_report = _impact_scorer_service.get_profiling_report
reset_impact_scorer = _impact_scorer_service.reset_impact_scorer
reset_profiling = _impact_scorer_service.reset_profiling

if TYPE_CHECKING:
    from enhanced_agent_bus.deliberation_layer.tensorrt_optimizer import TensorRTOptimizer
else:
    TensorRTOptimizer: TypeAlias = Any

_RuntimeTensorRTOptimizer: Any | None
try:
    from enhanced_agent_bus.deliberation_layer.tensorrt_optimizer import (
        TensorRTOptimizer as _RuntimeTensorRTOptimizer,
    )
except ImportError:
    try:
        from .tensorrt_optimizer import TensorRTOptimizer as _RuntimeTensorRTOptimizer
    except ImportError:
        _RuntimeTensorRTOptimizer = None

logger = get_logger(__name__)

try:
    import transformers  # noqa: F401

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import onnxruntime as _ort

    ONNX_AVAILABLE = True
except ImportError:
    _ort = None  # type: ignore[assignment]
    ONNX_AVAILABLE = False

try:
    import torch as _torch

    TORCH_AVAILABLE = True
except ImportError:
    _torch = None  # type: ignore[assignment]
    TORCH_AVAILABLE = False

try:
    import enhanced_agent_bus.profiling  # noqa: F401

    PROFILING_AVAILABLE = True
except (ImportError, Exception):
    PROFILING_AVAILABLE = False

_impact_scorer_instance: "ImpactScorer | None" = None

# Cached int8 ONNX session (built once at first get_impact_scorer() call)
_ort_session_cache: Any | None = None
_ort_tokenizer_cache: Any | None = None
_ORT_MAX_SEQ: int = 32  # Impact messages avg 6-12 tokens; seq=32 covers all cases
_ORT_CACHE_PATH: str = _os.path.join(
    _os.path.dirname(__file__), "optimized_models", "distilbert_int8_seq32.onnx"
)


def _build_ort_session() -> "tuple[Any, Any] | None":
    """Build and cache an int8 ONNX Runtime session for DistilBERT.

    Exports model to ONNX (torch.onnx.export) and quantizes to int8
    on first call. Result cached to disk at _ORT_CACHE_PATH.
    Returns (session, tokenizer) or None if prerequisites unavailable.
    """
    if not (ONNX_AVAILABLE and TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE):
        return None

    import os as _os2
    cache_path = _ORT_CACHE_PATH
    _os2.makedirs(_os2.path.dirname(cache_path), exist_ok=True)

    try:
        from transformers import AutoModel, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased", use_fast=True)

        if not _os2.path.exists(cache_path):
            # Export fp32 ONNX
            fp32_path = cache_path.replace("_int8_", "_fp32_")
            if not _os2.path.exists(fp32_path):
                logger.info("ImpactScorer: exporting DistilBERT to ONNX (first run, ~30s)...")
                model = AutoModel.from_pretrained("distilbert-base-uncased")
                model.eval()
                dummy = tokenizer(
                    "test", return_tensors="pt", padding="max_length",
                    truncation=True, max_length=_ORT_MAX_SEQ
                )
                cast(Any, _torch).onnx.export(
                    model,
                    (dummy["input_ids"], dummy["attention_mask"]),
                    fp32_path,
                    input_names=["input_ids", "attention_mask"],
                    output_names=["last_hidden_state"],
                    dynamic_axes={
                        "input_ids": {0: "batch", 1: "seq"},
                        "attention_mask": {0: "batch", 1: "seq"},
                        "last_hidden_state": {0: "batch", 1: "seq"},
                    },
                    opset_version=14,
                    do_constant_folding=True,
                )
                logger.info("ImpactScorer: ONNX export done → %s", fp32_path)

            # Quantize to int8
            logger.info("ImpactScorer: quantizing to int8...")
            from onnxruntime.quantization import QuantType, quantize_dynamic
            quantize_dynamic(fp32_path, cache_path, weight_type=QuantType.QInt8)
            logger.info("ImpactScorer: int8 quantization done → %s", cache_path)

        # Load session: sequential mode reduces thread contention under concurrent load
        opts = cast(Any, _ort).SessionOptions()
        opts.intra_op_num_threads = 4
        opts.graph_optimization_level = cast(Any, _ort).GraphOptimizationLevel.ORT_ENABLE_ALL
        session = cast(Any, _ort).InferenceSession(
            cache_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        logger.info("ImpactScorer: int8 ONNX session ready (seq=%d, CPU, threads=4)", _ORT_MAX_SEQ)
        return session, tokenizer

    except Exception as exc:
        logger.warning("ImpactScorer: int8 ONNX setup failed (%s), using keyword fallback", type(exc).__name__)
        return None


def get_impact_scorer(config: ScoringConfig | None = None, **kwargs: Any) -> "ImpactScorer":
    """Get or create a singleton instance of ImpactScorer."""
    global _impact_scorer_instance, _ort_session_cache, _ort_tokenizer_cache
    if _impact_scorer_instance is None:
        # Auto-configure structured logging if not already set up
        try:
            import logging as _logging

            from enhanced_agent_bus.observability.structured_logging import (
                configure_structured_logging,
            )
            if not _logging.getLogger().handlers:
                configure_structured_logging()
        except Exception:
            pass
        _impact_scorer_instance = ImpactScorer(config=config, **kwargs)
        # Build int8 ONNX session for fast ML inference (bypasses TensorRTOptimizer)
        if _ort_session_cache is None:
            result = _build_ort_session()
            if result is not None:
                _ort_session_cache, _ort_tokenizer_cache = result
                _impact_scorer_instance._ort_session = _ort_session_cache
                _impact_scorer_instance._ort_tokenizer = _ort_tokenizer_cache
                _impact_scorer_instance._bert_enabled = True
    return _impact_scorer_instance


def get_gpu_decision_matrix() -> "JSONDict":
    """Get GPU decision matrix from the global profiler."""
    try:
        from enhanced_agent_bus.profiling import get_global_profiler
        metrics = get_global_profiler().get_all_metrics()
        return {name: m.to_dict() for name, m in metrics.items()}
    except Exception:
        return _impact_scorer_service.get_gpu_decision_matrix()


def get_profiling_report() -> str:
    """Get profiling report from the global profiler."""
    try:
        from enhanced_agent_bus.profiling import get_global_profiler
        return get_global_profiler().generate_report()
    except Exception:
        return str(_impact_scorer_service.get_profiling_report())


class ImpactScorer:
    """
    Facade for impact scoring in the deliberation layer.

    Provides unified access to impact scoring capabilities including:
    - Basic semantic scoring via keyword matching
    - MiniCPM-enhanced 7-dimensional governance scoring (when enabled)
    - ONNX/TensorRT optimized inference for batch processing

    Constitutional Hash: 608508a9bd224290
    """

    def __init__(
        self,
        config: ScoringConfig | None = None,
        use_onnx: bool = False,
        enable_minicpm: bool = False,
        minicpm_model_name: str = "MiniCPM4-0.5B",
        prefer_minicpm_semantic: bool = True,
        enable_caching: bool = True,
        dtmc_learner: "DTMCLearner | None" = None,
        enable_loco_operator: bool = False,
        loco_operator_model: str = "LocoreMind/LocoOperator-4B-GGUF",
        loco_operator_device: str = "cpu",
        model_path: str | None = None,
        tokenizer_path: str | None = None,
    ) -> None:
        """
        Initialize the impact scorer.

        Args:
            config: Scoring configuration for weight and threshold tuning.
            use_onnx: Enable ONNX/TensorRT optimization for batch inference.
            enable_minicpm: Enable MiniCPM-enhanced semantic scoring.
            minicpm_model_name: MiniCPM model to use when enabled.
            prefer_minicpm_semantic: Prefer MiniCPM over basic semantic when available.
            enable_caching: Enable tiered caching for embeddings and scores.
            enable_loco_operator: Enable LocoOperator-4B governance scoring (MACI proposer).
            loco_operator_model: LocoOperator model identifier.
            loco_operator_device: Device for LocoOperator inference ('cpu', 'cuda', 'mps').
        """
        # Configure the impact scorer service with MiniCPM settings
        if enable_minicpm:
            configure_impact_scorer(
                enable_minicpm=True,
                minicpm_model_name=minicpm_model_name,
                minicpm_fallback_to_keywords=True,
                prefer_minicpm_semantic=prefer_minicpm_semantic,
            )

        self.service = get_impact_scorer_service()
        self.config = config or ScoringConfig()
        self._enable_minicpm = enable_minicpm

        # LocoOperator-4B integration (MACI proposer role)
        self._enable_loco_operator = enable_loco_operator
        self._loco_client: object | None = None
        if enable_loco_operator:
            try:
                from enhanced_agent_bus.deliberation_layer.loco_operator_client import (
                    LocoOperatorGovernanceClient,
                )
                from enhanced_agent_bus.llm_adapters.config import (
                    LocoOperatorAdapterConfig,
                )

                cfg = LocoOperatorAdapterConfig(
                    model=loco_operator_model,
                    device=loco_operator_device,
                    use_inference_api=False,
                )
                self._loco_client = LocoOperatorGovernanceClient(config=cfg)
                logger.info(
                    "ImpactScorer: LocoOperator-4B enabled (model=%s device=%s)",
                    loco_operator_model,
                    loco_operator_device,
                )
            except Exception as exc:
                logger.warning(
                    f"ImpactScorer: LocoOperator-4B init failed, continuing without it: {exc}"
                )
        self.model_name = "distilbert-base-uncased"
        self._bert_enabled = False
        self._onnx_enabled = use_onnx and ONNX_AVAILABLE

        # Attempt to load Rust DistilBERT model if paths provided or env var set
        _model_dir = model_path or _IMPACT_SCORER_MODEL_DIR or ""
        _tok_dir = tokenizer_path or _model_dir
        self._rust_scorer: object | None = None
        if _model_dir:
            try:
                from acgs_lite_rust import ImpactScorer as _RustImpactScorer  # type: ignore[import]

                self._rust_scorer = _RustImpactScorer(model_dir=_model_dir, device="cpu")
                self._bert_enabled = True
                import structlog as _sl

                _sl.get_logger(__name__).info(
                    "ImpactScorer: Rust DistilBERT loaded",
                    model_dir=_model_dir,
                )
            except (ImportError, OSError, RuntimeError) as _e:
                import structlog as _sl

                _sl.get_logger(__name__).warning(
                    "ImpactScorer: Rust model unavailable, falling back to keyword scoring",
                    error=type(_e).__name__,
                )
        self._enable_caching = enable_caching
        self._embedding_cache: TieredCacheManager | None = None

        if enable_caching and TieredCacheConfig is not None and TieredCacheManager is not None:
            cache_config = TieredCacheConfig(
                l1_maxsize=100,
                l1_ttl=300,
                l2_ttl=3600,
                l3_enabled=True,
                l3_ttl=86400,
            )
            self._embedding_cache = TieredCacheManager(
                config=cache_config, name="impact_embeddings"
            )

        self.high_impact_keywords = [
            "critical",
            "security",
            "emergency",
            "danger",
            "breach",
            "vulnerability",
            "exploit",
            "unauthorized",
            "suspicious",
            "transaction",
            "transfer",
            "payment",
            "violation",
            "regulation",
            "legal",
            "compliance",
            "audit",
            "governance",
            "attack",
            "threat",
            "compromise",
            "intrusion",
            "exfiltration",
            "alert",
            "execute_command",
            "transfer_funds",
        ]
        self._volume_counts: dict[str, int] = {}
        self._drift_history: dict[str, list[float]] = {}
        self._tokenization_cache: JSONDict = {}  # Cache for tokenized content
        # Direct int8 ONNX session (set by get_impact_scorer after _build_ort_session)
        self._ort_session: Any | None = None
        self._ort_tokenizer: Any | None = None
        # Tokenizer output cache: text → {"input_ids": np.array, "attention_mask": np.array}
        self._ort_tok_cache: dict[str, Any] = {}
        # Semantic score cache: text → float (safe since semantic score is pure fn of text)
        self._ort_score_cache: dict[str, float] = {}
        self._optimizer = None
        if self._onnx_enabled and _RuntimeTensorRTOptimizer is not None:
            self._optimizer = _RuntimeTensorRTOptimizer(self.model_name)
            # Try to load best backend
            if not (self._optimizer.load_tensorrt_engine() or self._optimizer.load_onnx_runtime()):
                logger.warning("Failed to load optimized backend, will use PyTorch fallback")

        # Pro2Guard DTMC trajectory scorer (6th dimension, Sprint 3).
        # Optional — when None, trajectory scoring is skipped (backward-compatible).
        self._dtmc_learner: Any | None = dtmc_learner

        # Spec-to-Artifact tracking (ref: solveeverything.org)
        # Tracks first-attempt governance decision accuracy continuously.
        self._total_evaluations: int = 0
        self._overrides: int = 0

    async def initialize(self) -> bool:
        """Initialize cache connections."""
        if self._embedding_cache:
            return cast(bool, await self._embedding_cache.initialize())
        return True

    async def close(self) -> None:
        """Close cache connections."""
        if self._embedding_cache:
            await self._embedding_cache.close()

    def _generate_cache_key(self, text: str) -> str:
        combined = f"{text}:{CONSTITUTIONAL_HASH}"
        return f"impact:embedding:{hashlib.sha256(combined.encode()).hexdigest()}"

    @classmethod
    def reset_class_cache(cls) -> None:
        """Reset class-level cache for testing compatibility."""
        pass

    def clear_tokenization_cache(self) -> None:
        """Clear the tokenization cache."""
        self._tokenization_cache.clear()

    @property
    def minicpm_available(self) -> bool:
        """Check if MiniCPM-enhanced scoring is available."""
        return bool(self.service.minicpm_available)

    @property
    def minicpm_enabled(self) -> bool:
        """Check if MiniCPM was requested at initialization."""
        return self._enable_minicpm

    @property
    def loco_operator_available(self) -> bool:
        """Check if LocoOperator-4B scoring is available.

        Constitutional Hash: 608508a9bd224290
        """
        if self._loco_client is None:
            return False
        return bool(getattr(self._loco_client, "is_available", False))

    async def _score_with_loco_operator(self, action: str, context: JSONDict) -> object | None:
        """Async governance scoring via LocoOperator-4B.

        MACI role: proposer — returns a GovernanceScoringResult or None on unavailability.

        Args:
            action: Description of the governance action to score.
            context: Structured message context.

        Returns:
            GovernanceScoringResult from LocoOperator, or None if unavailable/disabled.
        """
        if not self.loco_operator_available or self._loco_client is None:
            return None
        return cast(
            object | None,
            await cast(Any, self._loco_client).score_governance_action(action, context),
        )

    def get_governance_vector(self, context: JSONDict) -> dict[str, float] | None:
        """
        Get 7-dimensional governance impact vector.

        Returns a dictionary with scores for:
        - safety: Physical and operational safety impact
        - security: Information and system security impact
        - privacy: Personal data and confidentiality impact
        - fairness: Equity and bias considerations
        - reliability: System dependability impact
        - transparency: Explainability and auditability
        - efficiency: Resource and performance impact

        Args:
            context: Message context to analyze.

        Returns:
            Dict with governance dimension scores, or None if MiniCPM not available.
        """
        return self.service.get_governance_vector(context)

    def get_minicpm_score(self, context: JSONDict) -> ScoringResult | None:
        """
        Get impact score specifically from MiniCPM scorer.

        Args:
            context: Message context to analyze.

        Returns:
            ScoringResult from MiniCPM, or None if not available.
        """
        return self.service.get_minicpm_score(context)

    def score_impact(self, context: JSONDict) -> ScoringResult:
        """Get comprehensive impact score using the configured scoring methods."""
        return self.service.get_impact_score(context)

    def calculate_impact_score(
        self, message: JSONDict | object, context: JSONDict | None = None
    ) -> float:
        if PROFILING_AVAILABLE:
            from enhanced_agent_bus.profiling import get_global_profiler
            with get_global_profiler().track(self.model_name):
                return self._calculate_impact_score_impl(message, context)
        return self._calculate_impact_score_impl(message, context)

    def _calculate_impact_score_impl(
        self, message: JSONDict | object, context: JSONDict | None = None
    ) -> float:
        if context is None:
            context = {}

        # Handle None message gracefully
        if message is None:
            message = {}

        message_dict: JSONDict = (
            message
            if isinstance(message, dict)
            else cast(JSONDict, getattr(message, "__dict__", {}))
        )

        msg_from = (
            message.get("from_agent", "unknown")
            if isinstance(message, dict)
            else getattr(message, "from_agent", "unknown")
        )
        msg_priority = (
            context.get("priority")
            or (
                message.get("priority")
                if isinstance(message, dict)
                else getattr(message, "priority", "normal")
            )
            or "normal"
        )

        if hasattr(msg_priority, "name"):
            msg_priority = msg_priority.name.lower()
        else:
            msg_priority = str(msg_priority).lower()

        semantic_score = context.get("semantic_override")
        if semantic_score is None:
            semantic_score = self._calculate_semantic_score(message_dict)

        p_score = self._calculate_permission_score(message_dict)
        v_score = self._calculate_volume_score(str(msg_from))
        c_score = self._calculate_context_score(message_dict, context)
        d_score = self._calculate_drift_score(msg_from, 0.4)

        # Factors are now multiplicative with 1.0 as neutral
        p_factor = self._calculate_priority_factor(message_dict, context)
        t_factor = self._calculate_type_factor(message_dict, context)

        semantic_w = IMPACT_WEIGHT_SEMANTIC
        permission_w = IMPACT_WEIGHT_PERMISSION
        volume_w = IMPACT_WEIGHT_VOLUME
        context_w = IMPACT_WEIGHT_CONTEXT
        drift_w = IMPACT_WEIGHT_DRIFT

        base_score = (
            semantic_score * semantic_w
            + p_score * permission_w
            + v_score * volume_w
            + c_score * context_w
            + d_score * drift_w
        )

        final_score = base_score * p_factor * t_factor

        # Critical priority always gets high score
        if msg_priority == "critical":
            final_score = max(final_score, IMPACT_CRITICAL_FLOOR)

        # High semantic score (from high-impact keywords) should boost final score
        if semantic_score >= 0.9:
            final_score = max(final_score, IMPACT_HIGH_SEMANTIC_FLOOR)

        # 6th dimension: Pro2Guard DTMC trajectory risk (Sprint 3).
        # Active only when a DTMCLearner is attached AND the caller provides
        # trajectory_prefix (list[int] of ImpactLevel ordinals) in context.
        # IMPACT_WEIGHT_TRAJECTORY defaults to 0.0 → no change without opt-in.
        if self._dtmc_learner is not None and IMPACT_WEIGHT_TRAJECTORY > 0.0 and context:
            trajectory_prefix = context.get("trajectory_prefix")
            if trajectory_prefix:
                dtmc_risk = self._dtmc_learner.predict_risk(list(trajectory_prefix))
                final_score = min(1.0, final_score + dtmc_risk * IMPACT_WEIGHT_TRAJECTORY)
                logger.debug(
                    "ImpactScorer: DTMC trajectory risk=%.3f weight=%.3f → final=%.3f",
                    dtmc_risk,
                    IMPACT_WEIGHT_TRAJECTORY,
                    final_score,
                )

        self._total_evaluations += 1
        return float(min(1.0, final_score))

    def record_override(self) -> None:
        """Record a human override of a governance decision.

        Call when HITL review reverses an impact scorer decision (false positive
        or false negative corrected by human). Used to compute the Spec-to-Artifact
        Score (ref: solveeverything.org).
        """
        self._overrides += 1

    @property
    def spec_to_artifact_score(self) -> float:
        """Spec-to-Artifact Score: first-attempt governance accuracy.

        Measures what fraction of governance decisions are correct without
        retries or human override.

        Formula: (1 - override_rate)
        where override_rate = overrides / total_evaluations.

        Returns 1.0 when no evaluations have been performed yet.
        Ref: solveeverything.org — "percentage of times your AI stack
        produces working and safe code on the first try."
        """
        if self._total_evaluations == 0:
            return 1.0
        override_rate = self._overrides / self._total_evaluations
        return 1.0 - override_rate

    def get_spec_to_artifact_metrics(self) -> dict[str, int | float]:
        """Get detailed Spec-to-Artifact metrics for observability.

        Returns:
            Dict with total_evaluations, overrides, override_rate,
            and spec_to_artifact_score.
        """
        override_rate = (
            self._overrides / self._total_evaluations if self._total_evaluations > 0 else 0.0
        )
        return {
            "total_evaluations": self._total_evaluations,
            "overrides": self._overrides,
            "override_rate": override_rate,
            "spec_to_artifact_score": self.spec_to_artifact_score,
        }

    def _calculate_permission_score(self, message: dict[str, object] | object) -> float:
        if isinstance(message, dict):
            raw_tools = message.get("tools", [])
            tools = raw_tools if isinstance(raw_tools, list) else []
        else:
            raw_tools = getattr(message, "tools", [])
            tools = raw_tools if isinstance(raw_tools, list) else []
        if not tools:
            return 0.1

        # High-risk tool patterns
        high_risk_patterns = [
            "execute",
            "command",
            "shell",
            "bash",
            "sudo",
            "admin",
            "blockchain",
            "transfer",
            "payment",
            "funds",
            "delete",
            "modify",
            "update",
            "write",
            "create",
            "drop",
            "truncate",
        ]

        max_score = 0.1
        for tool in tools:
            tool_name = tool.get("name", "") if isinstance(tool, dict) else str(tool)
            tool_lower = tool_name.lower()

            # Check for high-risk patterns
            if any(pattern in tool_lower for pattern in high_risk_patterns):
                max_score = max(max_score, 0.7)
            elif "read" in tool_lower or "get" in tool_lower or "list" in tool_lower:
                max_score = max(max_score, 0.2)
            else:
                max_score = max(max_score, 0.3)

        return min(1.0, max_score)

    def _calculate_volume_score(self, agent_id: str) -> float:
        """Calculate volume-based score based on agent request history.

        Constitutional Hash: 608508a9bd224290
        """
        if not hasattr(self, "_agent_request_counts"):
            self._agent_request_counts: dict[str, int] = {}

        # Increment and get count
        count = self._agent_request_counts.get(agent_id, 0) + 1
        self._agent_request_counts[agent_id] = count

        # Scale score based on volume
        if count <= 10:
            return 0.1  # New agent baseline
        elif count <= 30:
            return 0.2
        elif count <= 50:
            return 0.5
        elif count <= 100:
            return 0.7
        else:
            return 1.0  # Very high volume

    def _calculate_context_score(self, message: JSONDict | object, context: JSONDict) -> float:
        base_score = 0.1

        if isinstance(message, dict):
            payload = message.get("payload", {})
        else:
            payload = getattr(message, "payload", getattr(message, "content", {}))
            if not isinstance(payload, dict):
                payload = {}

        if isinstance(payload, dict):
            amount = payload.get("amount", 0)
            if isinstance(amount, (int, float)) and amount >= 10000:
                base_score += 0.4

        return min(1.0, base_score)

    def _calculate_drift_score(self, agent_id: str, default: float) -> float:
        """Calculate behavioral drift score for an agent.

        Detects anomalous behavior by comparing current score to historical average.

        Constitutional Hash: 608508a9bd224290
        """
        if not hasattr(self, "_agent_score_history"):
            self._agent_score_history: dict[str, list[float]] = {}

        # Get agent's history
        history = self._agent_score_history.get(agent_id, [])

        # Store the current score
        self._agent_score_history.setdefault(agent_id, []).append(default)

        # Unknown or first request - no drift
        if len(history) < 2:
            return 0.0

        # Calculate average and deviation
        avg = sum(history) / len(history)
        deviation = abs(default - avg)

        # If deviation is significant, return drift score
        if deviation > 0.3:
            return min(1.0, deviation)

        return 0.0

    def score_messages_batch(self, messages: list[JSONDict]) -> list[float]:
        """Batch score impact for multiple messages using optimized inference."""
        if self._onnx_enabled and self._optimizer:
            if not NUMPY_AVAILABLE:
                raise ImportError("numpy is required for batch scoring")
            texts = [self._extract_text_content(m) for m in messages]
            # Use optimized batch inference
            embeddings = self._optimizer.infer_batch(texts)
            # For simplicity, calculate scores from embeddings (mock logic for now)
            # In real system, this would use a classification head on the embeddings
            scores = [float(np.mean(np.abs(emb)) * 2.0) for emb in embeddings]
            return [min(1.0, s) for s in scores]

        return [self.calculate_impact_score(m, {}) for m in messages]

    def batch_score_impact(
        self, messages: list[JSONDict], contexts: list[JSONDict] | None = None
    ) -> list[float]:
        """
        Batch score impact for multiple messages.
        """
        if not messages:
            return []
        if contexts is None:
            contexts = [{} for _ in range(len(messages))]
        elif len(contexts) != len(messages):
            raise ValueError(
                f"contexts length ({len(contexts)}) must match messages length ({len(messages)})"
            )
        if self._onnx_enabled and self._optimizer:
            return self.score_messages_batch(messages)

        merged_contexts = []
        for message, context in zip(messages, contexts, strict=False):
            merged_context = {**context}
            if isinstance(message, dict):
                merged_context["content"] = message.get("content", message)
            merged_contexts.append(merged_context)

        if (
            self._bert_enabled
            and self._rust_scorer is not None
            and hasattr(self._rust_scorer, "score_batch")
        ):
            try:
                batch_scores = self._rust_scorer.score_batch(
                    [self._extract_text_content(message) for message in messages]
                )
                return [float(score) for score in batch_scores]
            except Exception as exc:
                logger.warning(
                    "ImpactScorer: Rust batch scoring unavailable, falling back",
                    error=type(exc).__name__,
                )

        if self._enable_minicpm and hasattr(self.service, "get_impact_scores_batch"):
            try:
                batch_results = self.service.get_impact_scores_batch(merged_contexts)
                return [float(result.aggregate_score) for result in batch_results]
            except Exception as exc:
                logger.warning(
                    "ImpactScorer: service batch scoring unavailable, falling back",
                    error=type(exc).__name__,
                )

        return [self.calculate_impact_score(m, c) for m, c in zip(messages, contexts, strict=False)]

    def reset_history(self) -> None:
        """Reset internal history and caches."""
        if hasattr(self, "_agent_request_counts"):
            self._agent_request_counts.clear()
        if hasattr(self, "_agent_score_history"):
            self._agent_score_history.clear()
        self._volume_counts.clear()
        self._drift_history.clear()

    def _calculate_semantic_score(self, message: JSONDict) -> float:
        text = self._extract_text_content(message).strip().lower()
        if not text:
            return 0.0

        # Use optimized ONNX/TensorRT inference when available
        if self._onnx_enabled and self._optimizer is not None:
            try:
                # Track inference with profiler if available
                if PROFILING_AVAILABLE:
                    from enhanced_agent_bus.profiling import get_global_profiler

                    with get_global_profiler().track(self.model_name):
                        embeddings = self._optimizer.infer(text)
                else:
                    embeddings = self._optimizer.infer(text)

                # Convert embeddings to a score (mock logic for now, in real it would be a head)
                if NUMPY_AVAILABLE and isinstance(embeddings, np.ndarray):
                    score = float(np.mean(np.abs(embeddings)) * 2.0)
                    return min(1.0, max(0.0, score))
            except Exception as _e:
                logger.warning(
                    "ImpactScorer: Optimized inference error, falling back",
                    error=type(_e).__name__,
                )

        # Use direct int8 ONNX session when available (fastest path, no TensorRTOptimizer)
        if self._ort_session is not None and self._ort_tokenizer is not None:
            try:
                # Check semantic score cache first (semantic score is pure fn of text)
                cached_score = self._ort_score_cache.get(text)
                if cached_score is not None:
                    return cached_score

                # Cache tokenized inputs by text to avoid redundant tokenization
                cached = self._ort_tok_cache.get(text)
                if cached is None:
                    tok_out = cast(Any, self._ort_tokenizer)(
                        text,
                        return_tensors="np",
                        padding="max_length",
                        truncation=True,
                        max_length=_ORT_MAX_SEQ,
                    )
                    cached = {"input_ids": tok_out["input_ids"], "attention_mask": tok_out["attention_mask"]}
                    if len(self._ort_tok_cache) < 512:  # bound cache size
                        self._ort_tok_cache[text] = cached
                outputs = cast(Any, self._ort_session).run(None, cached)
                # Mean-pool last hidden state → scalar score
                last_hidden = outputs[0]  # (1, seq, 768)
                if NUMPY_AVAILABLE:
                    score = float(np.mean(np.abs(last_hidden)) * 2.0)
                    score = min(1.0, max(0.0, score))
                    if len(self._ort_score_cache) < 512:  # bound cache size
                        self._ort_score_cache[text] = score
                    return score
            except Exception as _e:
                logger.warning(
                    "ImpactScorer: int8 ONNX inference error, falling back to keywords",
                    error=type(_e).__name__,
                )

        # Use Rust DistilBERT when available — do NOT fall through to keywords
        if self._bert_enabled and self._rust_scorer is not None:
            try:
                return float(self._rust_scorer.score(text))  # type: ignore[union-attr]
            except Exception as _e:
                import structlog as _sl

                _sl.get_logger(__name__).warning(
                    "ImpactScorer: Rust scorer error, falling back to keywords",
                    error=type(_e).__name__,
                )
        if any(kw in text for kw in self.high_impact_keywords):
            return 0.95
        return 0.1

    def _get_keyword_score(self, text: str) -> float:
        text_lower = text.lower()
        matched_count = sum(1 for kw in self.high_impact_keywords if kw in text_lower)
        if matched_count == 0:
            return 0.1
        if matched_count == 1:
            return 0.5
        if matched_count == 2:
            return 0.75
        return min(1.0, 0.75 + (matched_count - 2) * 0.1)

    def _calculate_priority_factor(
        self, message: JSONDict, context: JSONDict | None = None
    ) -> float:
        """Calculate priority factor in range 0-1.

        Constitutional Hash: 608508a9bd224290
        """
        if context is None:
            context = {}
        priority = (
            context.get("priority")
            or (
                message.get("priority")
                if isinstance(message, dict)
                else getattr(message, "priority", "normal")
            )
            or "normal"
        )

        # Handle Priority enum
        if hasattr(priority, "value"):
            priority = priority.value
        if hasattr(priority, "name"):
            priority = priority.name.lower()

        # Convert to string for comparison
        priority = str(priority).lower()

        # Return values in 0-1 range as tests expect
        if priority in ["critical", "3"]:
            return 1.0
        if priority in ["high", "2"]:
            return 0.8
        if priority in ["medium", "normal", "1"]:
            return 0.5
        if priority in ["low", "0"]:
            return 0.2
        return 0.5  # Default for unknown priority

    def _calculate_type_factor(self, message: JSONDict, context: JSONDict | None = None) -> float:
        m_type = (
            message.get("message_type", "")
            if isinstance(message, dict)
            else getattr(message, "message_type", "")
        )
        if m_type == "governance":
            return 1.5
        if m_type == "security":
            return 1.4
        if m_type == "financial":
            return 1.3
        return 1.0

    def _extract_text_content(self, message: dict[str, object] | object) -> str:
        """Extract text content from message for semantic analysis."""
        content_parts = []

        # Extract basic content
        content_parts.extend(self._extract_basic_content(message))

        # Extract payload content (for dict messages)
        if isinstance(message, dict):
            content_parts.extend(self._extract_payload_content(message))

        # Extract tool content
        content_parts.extend(self._extract_tool_content(message))

        return " ".join(content_parts)

    def _extract_basic_content(self, message: dict[str, object] | object) -> list[str]:
        """Extract basic content from message."""
        content_parts = []

        if hasattr(message, "content"):
            content_parts.append(str(message.content))
        elif isinstance(message, dict) and "content" in message:
            content_parts.append(str(message["content"]))

        return content_parts

    def _extract_payload_content(self, message: dict[str, object]) -> list[str]:
        """Extract payload and key-based content from dict message."""
        content_parts = []

        # Payload message
        if "payload" in message and isinstance(message["payload"], dict):
            payload = message["payload"]
            if "message" in payload:
                content_parts.append(str(payload["message"]))

        # Key-based content
        for key in ("action", "details", "description", "text"):
            if key in message:
                content_parts.append(str(message[key]))

        return content_parts

    def _extract_tool_content(self, message: dict[str, object] | object) -> list[str]:
        """Extract tool names for keyword matching."""
        content_parts = []

        # Get tools list
        tools: list[object] = []
        if isinstance(message, dict):
            raw_tools = message.get("tools", [])
            tools = raw_tools if isinstance(raw_tools, list) else []
        elif hasattr(message, "tools"):
            raw_tools = message.tools or []
            tools = raw_tools if isinstance(raw_tools, list) else []

        # Extract tool names
        for tool in tools:
            if isinstance(tool, dict):
                content_parts.append(tool.get("name", ""))
            else:
                content_parts.append(str(tool))

        return content_parts

    async def _get_embeddings(self, text: str) -> Any:
        """Get embeddings for text, with fallback for when model is not available.

        Constitutional Hash: 608508a9bd224290
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required for embedding generation")

        if self._embedding_cache:
            cache_key = self._generate_cache_key(text)
            cached_embedding = await self._embedding_cache.get_async(cache_key)
            if cached_embedding is not None:
                if isinstance(cached_embedding, str):
                    import json

                    cached_embedding = json.loads(cached_embedding)
                logger.info(f"Embedding cache HIT for text length {len(text)}")
                return np.array(cached_embedding)
            logger.debug(f"Embedding cache MISS for text length {len(text)}")

        embedding = np.zeros((1, 768))

        if self._embedding_cache and cached_embedding is None:
            await self._embedding_cache.set(cache_key, embedding.tolist(), ttl=3600)

        return embedding

    def _get_keyword_embeddings(self) -> Any:
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy is required for keyword embeddings")
        return np.array([[0.1] * 768])


__all__ = [
    # Constants
    "CONSTITUTIONAL_HASH",
    # Main class
    "ImpactScorer",
    "ImpactScoringConfig",
    # Models
    "ImpactVector",
    # Configuration
    "ScoringConfig",
    "ScoringMethod",
    "ScoringResult",
    # Factory functions
    "calculate_message_impact",
    "configure_impact_scorer",
    # Utility functions
    "cosine_similarity_fallback",
    "get_gpu_decision_matrix",
    "get_impact_scorer",
    "get_impact_scorer_service",
    "get_profiling_report",
    "reset_impact_scorer",
    "reset_profiling",
]
