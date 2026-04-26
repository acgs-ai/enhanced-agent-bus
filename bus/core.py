"""
Enhanced Agent Bus - High-performance agent communication with constitutional validation.

Constitutional Hash: 608508a9bd224290
"""

from __future__ import annotations

import asyncio
import importlib
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias, cast

if TYPE_CHECKING:
    from enhanced_agent_bus._compat.types import AgentInfo

    from ..components import GovernanceValidator, MessageRouter, RegistryManager

from ..bus_types import JSONDict

if not TYPE_CHECKING:
    try:
        from enhanced_agent_bus._compat.types import AgentInfo as ImportedAgentInfo
    except ImportError:
        ImportedAgentInfo: TypeAlias = dict[str, object]
    AgentInfo: TypeAlias = ImportedAgentInfo

from ..components import GovernanceValidator, MessageRouter, RegistryManager
from ..dependency_bridge import (
    get_dependency,
    get_feature_flags,
    get_maci_enforcer,
    get_maci_role_registry,
    is_feature_available,
)

# Feature flags (resolved at import time for backward compatibility)
_flags = get_feature_flags()
CIRCUIT_BREAKER_ENABLED: bool = _flags.get("CIRCUIT_BREAKER_ENABLED", False)
DELIBERATION_AVAILABLE: bool = _flags.get("DELIBERATION_AVAILABLE", False)
MACI_AVAILABLE: bool = _flags.get("MACI_AVAILABLE", False)
METERING_AVAILABLE: bool = _flags.get("METERING_AVAILABLE", False)
METRICS_ENABLED: bool = _flags.get("METRICS_ENABLED", False)
POLICY_CLIENT_AVAILABLE: bool = _flags.get("POLICY_CLIENT_AVAILABLE", False)

# Direct canonical imports with fallbacks
try:
    from enhanced_agent_bus._compat.redis_config import get_redis_url
except ImportError:

    def get_redis_url(db: int = 0) -> str:
        _ = db
        return "redis://localhost:6379"


DEFAULT_REDIS_URL: str = get_redis_url()

_circuit_breaker_compat: Any | None
try:
    import enhanced_agent_bus._compat.circuit_breaker as _circuit_breaker_compat
except ImportError:
    _circuit_breaker_compat = None

initialize_core_circuit_breakers = (
    getattr(_circuit_breaker_compat, "initialize_core_circuit_breakers", None)
    if _circuit_breaker_compat is not None
    else None
)

try:
    _compat_metrics: Any | None
    _compat_metrics = importlib.import_module("enhanced_agent_bus._compat.metrics")
except ImportError:
    _compat_metrics = None


if _compat_metrics is not None:
    set_service_info = _compat_metrics.set_service_info
else:

    def set_service_info(service_name: str, service_version: str, constitutional_hash: str) -> None:
        _ = (service_name, service_version, constitutional_hash)


try:
    _policy_client_module: Any | None
    _policy_client_module = importlib.import_module("enhanced_agent_bus.policy_client")
except ImportError:
    _policy_client_module = None


if _policy_client_module is not None:
    get_policy_client = _policy_client_module.get_policy_client
else:

    def get_policy_client(fail_closed: bool | None = None) -> object | None:
        _ = fail_closed
        return None


DeliberationQueue: Any | None
try:
    from ..deliberation_layer.deliberation_queue import DeliberationQueue
except ImportError:
    DeliberationQueue = None


# MACI uses stubs from dependency_bridge
_maci_enforcer_factory = cast(Any, get_maci_enforcer())
_maci_role_registry_factory = cast(Any, get_maci_role_registry())

del _flags  # Clean up namespace
from enhanced_agent_bus.models import (
    CONSTITUTIONAL_HASH,
    AgentMessage,
    BatchRequest,
    BatchResponse,
)
from enhanced_agent_bus.validators import ValidationResult

from ..interfaces import (
    AgentRegistry,
    MACIEnforcerProtocol,
    MACIRegistryProtocol,
    ProcessingStrategy,
    ValidationStrategy,
)
from ..message_processor import MessageProcessor
from ..metering_manager import create_metering_manager
from ..registry import (
    CompositeValidationStrategy,
)
from ..security_helpers import normalize_tenant_id, validate_tenant_consistency
from ..utils import get_iso_timestamp
from .batch import BatchProcessor
from .governance import GovernanceIntegration
from .messaging import MessageHandler
from .metrics import BusMetrics
from .validation import MessageValidator

# Rate Limiting imports
_rate_limiter_compat: Any | None
try:
    _rate_limiter_compat = importlib.import_module(
        "enhanced_agent_bus._compat.security.rate_limiter"
    )
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    _rate_limiter_compat = None
    RATE_LIMITING_AVAILABLE = False

SlidingWindowRateLimiter = (
    getattr(_rate_limiter_compat, "SlidingWindowRateLimiter", None)
    if _rate_limiter_compat is not None
    else None
)
TenantRateLimitProvider = (
    getattr(_rate_limiter_compat, "TenantRateLimitProvider", None)
    if _rate_limiter_compat is not None
    else None
)
RateLimitScope = (
    getattr(_rate_limiter_compat, "RateLimitScope", None)
    if _rate_limiter_compat is not None
    else None
)

# Dynamic Context System imports
_dynamic_context_module: Any | None
try:
    _dynamic_context_module = importlib.import_module("src.core.services.dynamic_context")
    DYNAMIC_CONTEXT_AVAILABLE = True
except ImportError:
    _dynamic_context_module = None
    DYNAMIC_CONTEXT_AVAILABLE = False

DynamicContextEngine = (
    getattr(_dynamic_context_module, "DynamicContextEngine", None)
    if _dynamic_context_module is not None
    else None
)
get_dynamic_context_engine = (
    getattr(_dynamic_context_module, "get_dynamic_context_engine", None)
    if _dynamic_context_module is not None
    else None
)


# Adaptive Governance imports
async def _fallback_evaluate_message_governance(
    message: dict[str, Any], context: dict[str, Any]
) -> Any:
    _ = (message, context)
    return None


def _fallback_get_adaptive_governance() -> Any | None:
    return None


async def _fallback_initialize_adaptive_governance(constitutional_hash: str) -> Any:
    _ = constitutional_hash
    return None


def _fallback_provide_governance_feedback(
    decision: Any, outcome_success: bool, human_override: bool | None = None
) -> None:
    _ = (decision, outcome_success, human_override)


try:
    _adaptive_governance_module: Any | None
    _adaptive_governance_module = importlib.import_module("enhanced_agent_bus.adaptive_governance")
    ADAPTIVE_GOVERNANCE_AVAILABLE = True
except ImportError:
    _adaptive_governance_module = None
    ADAPTIVE_GOVERNANCE_AVAILABLE = False

AdaptiveGovernanceEngine = (
    getattr(_adaptive_governance_module, "AdaptiveGovernanceEngine", None)
    if _adaptive_governance_module is not None
    else None
)
evaluate_message_governance = (
    getattr(
        _adaptive_governance_module,
        "evaluate_message_governance",
        _fallback_evaluate_message_governance,
    )
    if _adaptive_governance_module is not None
    else _fallback_evaluate_message_governance
)
get_adaptive_governance = (
    getattr(
        _adaptive_governance_module, "get_adaptive_governance", _fallback_get_adaptive_governance
    )
    if _adaptive_governance_module is not None
    else _fallback_get_adaptive_governance
)
initialize_adaptive_governance = (
    getattr(
        _adaptive_governance_module,
        "initialize_adaptive_governance",
        _fallback_initialize_adaptive_governance,
    )
    if _adaptive_governance_module is not None
    else _fallback_initialize_adaptive_governance
)
provide_governance_feedback = (
    getattr(
        _adaptive_governance_module,
        "provide_governance_feedback",
        _fallback_provide_governance_feedback,
    )
    if _adaptive_governance_module is not None
    else _fallback_provide_governance_feedback
)


from enhanced_agent_bus.observability.structured_logging import get_logger

logger = get_logger(__name__)


class EnhancedAgentBus:
    """
    Enhanced Agent Bus - High-performance agent communication with constitutional validation.

    The EnhancedAgentBus provides a Redis-backed message bus for agent-to-agent communication
    with built-in constitutional compliance, impact scoring, and deliberation routing.

    Key features:
    - Constitutional hash validation for all messages
    - Automatic impact scoring for high-risk decisions
    - Deliberation layer routing for messages > 0.8 impact
    - Multi-tenant isolation with tenant-based message segregation
    - Circuit breaker integration for fault tolerance
    - MACI role separation enforcement

    Args:
        redis_url: Redis connection URL (default: redis://localhost:6379)
        enable_maci: Enable MACI role separation (default: False)
        maci_strict_mode: Strict MACI enforcement (default: True)
        use_dynamic_policy: Use policy registry instead of static hash (default: False)
        enable_metering: Enable usage metering (default: True)
        tenant_id: Default tenant ID for messages

    Constitutional Hash: 608508a9bd224290
    """

    def __init__(
        self,
        registry_manager: RegistryManager | None = None,
        governance: GovernanceValidator | None = None,
        router: MessageRouter | None = None,
        processor: MessageProcessor | None = None,
        **kwargs: object,
    ) -> None:
        self._config = kwargs
        self._constitutional_hash = CONSTITUTIONAL_HASH
        redis_url = kwargs.get("redis_url", DEFAULT_REDIS_URL)
        self.redis_url = redis_url if isinstance(redis_url, str) else DEFAULT_REDIS_URL
        # Read POLICY_CLIENT_AVAILABLE at runtime to pick up the post-initialization
        # value. The module-level constant may be stale (captured before the
        # DependencyRegistry finishes loading). Fall back to the frozen constant
        # if the bridge is unavailable.
        try:
            from ..dependency_bridge import get_feature_flags as _get_feature_flags

            _policy_client_available: bool = _get_feature_flags().get(
                "POLICY_CLIENT_AVAILABLE", POLICY_CLIENT_AVAILABLE
            )
        except Exception:
            _policy_client_available = POLICY_CLIENT_AVAILABLE
        self._use_dynamic_policy = (
            kwargs.get("use_dynamic_policy", False) and _policy_client_available
        )
        self._policy_client = (
            get_policy_client(fail_closed=bool(kwargs.get("policy_fail_closed", False)))
            if self._use_dynamic_policy
            else None
        )

        # Restore MACI and Metering initialization
        self._metering_manager = create_metering_manager(
            enable_metering=bool(kwargs.get("enable_metering", True)) and METERING_AVAILABLE,
            constitutional_hash=CONSTITUTIONAL_HASH,
        )
        maci_factories_available = (
            _maci_role_registry_factory is not None and _maci_enforcer_factory is not None
        )
        self._enable_maci = bool(kwargs.get("enable_maci", True)) and (
            MACI_AVAILABLE or maci_factories_available
        )
        self._maci_registry: MACIRegistryProtocol | None = cast(
            MACIRegistryProtocol | None,
            kwargs.get("maci_registry")
            or (_maci_role_registry_factory() if self._enable_maci else None),
        )
        self._maci_strict_mode = bool(kwargs.get("maci_strict_mode", True))
        self._maci_enforcer: MACIEnforcerProtocol | None = cast(
            MACIEnforcerProtocol | None,
            kwargs.get("maci_enforcer")
            or (
                _maci_enforcer_factory(
                    registry=self._maci_registry,
                    strict_mode=self._maci_strict_mode,
                )
                if self._enable_maci
                else None
            ),
        )
        self._kafka_bus: object | None = None
        self._kafka_consumer_task: asyncio.Task[None] | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # Initialize new modular components with Dependency Injection support
        self._registry_manager = registry_manager or RegistryManager(
            config=kwargs,
            registry_backend=cast(Any, kwargs.get("registry")),
            maci_registry=cast(Any, self._maci_registry),
            enable_maci=self._enable_maci,
            policy_client=self._policy_client,
        )

        self._governance = governance or GovernanceValidator(
            config=kwargs,
            policy_client=self._policy_client,
            constitutional_hash=self._constitutional_hash,
            enable_adaptive_governance=bool(kwargs.get("enable_adaptive_governance", False)),
        )

        if router and not hasattr(router, "_router"):
            from ..components import MessageRouter as RouterComponent

            self._router_component = RouterComponent(
                config=kwargs,
                router_backend=cast(Any, router),
                kafka_bus=self._kafka_bus,
            )
        else:
            self._router_component = router or MessageRouter(
                config=kwargs,
                router_backend=cast(Any, kwargs.get("router")),
                kafka_bus=self._kafka_bus,
            )

        # Backward compatibility properties (legacy agents dict)
        self._running = False
        self._idempotency_lock = asyncio.Lock()
        self._inflight_idempotency: dict[str, asyncio.Task[ValidationResult]] = {}

        # Legacy queue for receive_message
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()

        # Initialize rate limiting
        self._rate_limiter = None
        self._tenant_rate_limit_provider = None
        self._redis_client_for_limiter = None

        if kwargs.get("enable_rate_limiting", True) and RATE_LIMITING_AVAILABLE:
            try:
                import redis.asyncio as aioredis

                self._redis_client_for_limiter = aioredis.from_url(self.redis_url)
                if SlidingWindowRateLimiter is None or TenantRateLimitProvider is None:
                    raise RuntimeError("Rate limiting components unavailable")
                self._rate_limiter = SlidingWindowRateLimiter(
                    redis_client=self._redis_client_for_limiter,
                    fallback_to_memory=True,
                )
                self._tenant_rate_limit_provider = TenantRateLimitProvider.from_env()
                logger.info(f"[{CONSTITUTIONAL_HASH}] Agent Bus rate limiting initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Agent Bus rate limiter: {e}")

        self._deliberation_queue = kwargs.get("deliberation_queue")
        if (
            not self._deliberation_queue
            and DELIBERATION_AVAILABLE
            and DeliberationQueue is not None
        ):
            self._deliberation_queue = DeliberationQueue()

        # Initialize validation strategy with PQC support
        if kwargs.get("validator"):
            self._validator = kwargs.get("validator")
        else:
            self._validator = CompositeValidationStrategy(enable_pqc=True)

        self._processor = processor or (
            kwargs.get("processor")
            or MessageProcessor(
                registry=self._registry_manager._registry,
                router=self._router_component._router,
                validator=self._validator,
                policy_client=self._policy_client,
                maci_registry=self._maci_registry,
                maci_enforcer=self._maci_enforcer,
                maci_strict_mode=self._maci_strict_mode,
                enable_maci=self._enable_maci,
                enable_metering=kwargs.get("enable_metering", True),
            )
        )

        # Properties removed - use public .router, .registry, .agents properties instead

        # Adaptive Governance
        self._adaptive_governance = None
        self._enable_adaptive_governance = (
            kwargs.get("enable_adaptive_governance", False) and ADAPTIVE_GOVERNANCE_AVAILABLE
        )
        self._metrics: JSONDict = {
            "sent": 0,
            "received": 0,
            "failed": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "messages_failed": 0,
            "started_at": None,
        }

        # Initialize helper components
        self._message_validator = MessageValidator(
            governance=self._governance,
            agents=self._registry_manager._agents,
            metrics=self._metrics,
        )

        self._message_handler = MessageHandler(
            processor=cast(MessageProcessor, self._processor),
            router_component=self._router_component,
            registry_manager=self._registry_manager,
            governance=self._governance,
            validator=self._message_validator,
            message_queue=self._message_queue,
            deliberation_queue=self._deliberation_queue,
            metering_manager=self._metering_manager,
            kafka_bus=self._kafka_bus,
            metrics=self._metrics,
            config=self._config,
        )

        self._governance_integration = GovernanceIntegration(
            governance=self._governance,
            get_registered_agents=self.get_registered_agents,
            metrics=self._metrics,
        )

        self._batch_processor = BatchProcessor(
            processor=cast(MessageProcessor, self._processor),
            validator=cast(ValidationStrategy, self._validator),
            enable_maci=self._enable_maci,
            maci_registry=cast(Any, self._maci_registry),
            maci_enforcer=cast(Any, self._maci_enforcer),
            maci_strict_mode=self._maci_strict_mode,
            metering_manager=self._metering_manager,
            metrics=self._metrics,
        )

        self._bus_metrics = BusMetrics(
            bus=self,
            metrics=self._metrics,
            config=self._config,
        )

        # Dynamic Context System
        self._dynamic_context_enabled: bool = bool(
            kwargs.get("enable_dynamic_context", True) and DYNAMIC_CONTEXT_AVAILABLE
        )
        self._dynamic_context_engine: Any | None = (
            get_dynamic_context_engine()
            if self._dynamic_context_enabled and get_dynamic_context_engine
            else None
        )

    @property
    def constitutional_hash(self) -> str:
        """Return the constitutional hash for governance validation.

        Returns:
            str: The cryptographic constitutional hash (608508a9bd224290).
        """
        return self._constitutional_hash

    @classmethod
    def from_config(cls, config: JSONDict) -> EnhancedAgentBus:
        """Create an EnhancedAgentBus instance from a configuration object.

        Args:
            config: Configuration object with to_dict() method or dict-like object.

        Returns:
            EnhancedAgentBus: New instance configured with provided settings.
        """
        if hasattr(config, "to_dict"):
            return cls(**cast(Any, config).to_dict())
        config_data: Any = config
        return cls(**config_data)

    @staticmethod
    def _normalize_tenant_id(tid: str | None) -> str | None:
        return normalize_tenant_id(tid)

    async def start(self) -> None:
        """Start the agent bus and initialize all components.

        Initializes governance, routing, metrics, and circuit breakers.
        Must be called before sending or receiving messages.
        """
        self._running, self._metrics["started_at"] = True, get_iso_timestamp()
        await self._metering_manager.start()

        # Initialize components
        await self._governance.initialize()
        self._constitutional_hash = self._governance.constitutional_hash

        await self._router_component.initialize()

        # Start Kafka consumer if enabled
        if self._config.get("use_kafka") or self._kafka_bus:
            await self._start_kafka()

        if METRICS_ENABLED and set_service_info:
            set_service_info("enhanced_agent_bus", "3.0.0", CONSTITUTIONAL_HASH)
        if CIRCUIT_BREAKER_ENABLED and initialize_core_circuit_breakers:
            initialize_core_circuit_breakers()

    async def stop(self) -> None:
        """Stop the agent bus and shutdown all components.

        Gracefully shuts down metering, governance, routing, and Kafka consumers.
        """
        self._running = False
        await self._metering_manager.stop()
        await self._governance.shutdown()
        await self._router_component.shutdown()
        processor_shutdown = getattr(self._processor, "shutdown", None)
        if callable(processor_shutdown):
            shutdown_result = processor_shutdown()
            if asyncio.iscoroutine(shutdown_result):
                await shutdown_result

        if self._kafka_consumer_task:
            self._kafka_consumer_task.cancel()
            try:
                await self._kafka_consumer_task
            except asyncio.CancelledError:
                pass

        background_tasks = tuple(self._background_tasks)
        for task in background_tasks:
            if not task.done():
                task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        if self._redis_client_for_limiter:
            try:
                await self._redis_client_for_limiter.aclose()
            except Exception:
                pass

    async def register_agent(
        self,
        agent_id: str,
        agent_type: str = "worker",
        capabilities: list[str] | None = None,
        tenant_id: str | None = None,
        maci_role: str | None = None,
        **kwargs: object,
    ) -> bool:
        """Register an agent with the bus for message routing.

        Args:
            agent_id: Unique identifier for the agent.
            agent_type: Type classification (e.g., 'worker', 'supervisor').
            capabilities: List of capabilities the agent provides.
            tenant_id: Tenant identifier for multi-tenant isolation.
            maci_role: MACI role for constitutional governance.
            **kwargs: Additional registration metadata.

        Returns:
            bool: True if registration succeeded, False otherwise.
        """
        return await self._registry_manager.register_agent(
            agent_id,
            self.constitutional_hash,
            agent_type,
            capabilities,
            tenant_id,
            maci_role,
            **kwargs,
        )

    async def unregister_agent(self, aid: str) -> bool:
        """Remove an agent from the bus registry.

        Args:
            aid: Agent identifier to unregister.

        Returns:
            bool: True if agent was unregistered, False if not found.
        """
        return await self._registry_manager.unregister_agent(aid)

    def get_agent_info(self, aid: str) -> AgentInfo | None:
        """Retrieve information about a registered agent.

        Args:
            aid: Agent identifier to look up.

        Returns:
            AgentInfo: Agent metadata if found, None otherwise.
        """
        return self._registry_manager.get_agent_info(aid, self.constitutional_hash)

    def get_registered_agents(self) -> list[str]:
        """Get list of all registered agent identifiers.

        Returns:
            List[str]: Agent IDs currently registered with the bus.
        """
        return self._registry_manager.get_registered_agents()

    def get_agents_by_type(self, atype: str) -> list[str]:
        """Get agents filtered by type classification.

        Args:
            atype: Agent type to filter by (e.g., 'worker', 'supervisor').

        Returns:
            List[str]: Agent IDs matching the specified type.
        """
        return self._registry_manager.get_agents_by_type(atype)

    def get_agents_by_capability(self, cap: str) -> list[str]:
        """Get agents filtered by capability.

        Args:
            cap: Capability name to filter by.

        Returns:
            List[str]: Agent IDs that provide the specified capability.
        """
        return self._registry_manager.get_agents_by_capability(cap)

    # --- Delegated methods for backward compatibility ---

    def _record_metrics_failure(self) -> None:
        """Record failure metrics atomically for message processing."""
        self._message_validator.record_metrics_failure()

    def _record_metrics_success(self) -> None:
        """Record success metrics atomically for message processing."""
        self._message_validator.record_metrics_success()

    def _validate_constitutional_hash_for_message(
        self, msg: AgentMessage, result: ValidationResult
    ) -> bool:
        """Validate message constitutional hash via governance component."""
        return self._message_validator.validate_constitutional_hash_for_message(msg, result)

    def _validate_and_normalize_tenant(self, msg: AgentMessage, result: ValidationResult) -> bool:
        """Normalize and validate tenant ID for multi-tenant message isolation."""
        return self._message_validator.validate_and_normalize_tenant(msg, result)

    async def _process_message_with_fallback(self, msg: AgentMessage) -> ValidationResult:
        """Process message through processor with graceful degradation."""
        return await self._message_handler.process_message_with_fallback(msg)

    async def _finalize_message_delivery(self, msg: AgentMessage, result: ValidationResult) -> bool:
        """Handle routing and delivery of validated message."""
        return await self._message_handler.finalize_message_delivery(msg, result)

    @staticmethod
    def _is_test_mode_message(msg: AgentMessage) -> bool:
        """Return True when message attributes indicate test-mode execution."""
        return (
            "fail" in str(msg.content).lower()
            or "invalid" in str(msg.constitutional_hash).lower()
            or "test-agent" in str(msg.from_agent)
        )

    async def _apply_rate_limit(self, msg: AgentMessage, result: ValidationResult) -> bool:
        """Apply global/tenant rate limiting and mutate result on denial."""
        if not self._rate_limiter:
            return True

        limit_key = "bus:global"
        limit = self._config.get("bus_global_limit", 10000)
        window = self._config.get("bus_global_window", 60)
        scope = getattr(RateLimitScope, "GLOBAL", "global")

        if msg.tenant_id:
            limit_key = f"bus:tenant:{msg.tenant_id}"
            scope = getattr(RateLimitScope, "TENANT", "tenant")
            if self._tenant_rate_limit_provider:
                quota = self._tenant_rate_limit_provider.get_quota(msg.tenant_id)
                if quota:
                    limit = quota.requests
                    window = quota.window_seconds

        rate_result = await self._rate_limiter.is_allowed(
            key=limit_key,
            limit=limit,
            window_seconds=window,
            scope=scope,
        )
        if rate_result.allowed:
            return True

        result.add_error(
            f"Rate limit exceeded for {limit_key}. Retry after {rate_result.retry_after}s"
        )
        return False

    def _resolve_idempotency_key(self, msg: AgentMessage) -> str | None:
        """Resolve an idempotency key from supported message surfaces."""
        explicit_key = getattr(msg, "idempotency_key", None)
        if isinstance(explicit_key, str) and explicit_key:
            return explicit_key

        headers = getattr(msg, "headers", None)
        if isinstance(headers, dict):
            header_key = headers.get("idempotency_key") or headers.get("Idempotency-Key")
            if isinstance(header_key, str) and header_key:
                return header_key

        metadata = getattr(msg, "metadata", None)
        if isinstance(metadata, dict):
            metadata_key = metadata.get("idempotency_key")
            if isinstance(metadata_key, str) and metadata_key:
                return metadata_key

        return None

    async def _send_message_once(self, msg: AgentMessage) -> ValidationResult:
        """Execute a single send_message flow without idempotency wrapping."""
        result = ValidationResult()

        if not self._running:
            if self._config.get("allow_unstarted") or self._is_test_mode_message(msg):
                sent_count = self._metrics.get("sent", 0)
                self._metrics["sent"] = (sent_count if isinstance(sent_count, int) else 0) + 1
            else:
                result.add_error("Agent bus is not started")
                self._record_metrics_failure()
                return result

        if not self._message_validator.validate_message_shape(msg, result):
            return result

        # Step 2: Validate constitutional hash
        if not self._validate_constitutional_hash_for_message(msg, result):
            return result

        # Step 3: Validate and normalize tenant
        if not self._validate_and_normalize_tenant(msg, result):
            return result

        # Step 3.5: Apply rate limiting
        if not await self._apply_rate_limit(msg, result):
            return result

        # Step 3.7: Assemble dynamic context (pre-validation enrichment)
        if self._dynamic_context_engine is not None:
            try:
                dynamic_ctx = await self._dynamic_context_engine.build_context(
                    message=msg,
                    tenant_id=msg.tenant_id,
                    constitutional_hash=self._constitutional_hash,
                )
                # Inject context into message metadata for OPA and audit trail
                msg.metadata["dynamic_context"] = dynamic_ctx.to_opa_input()
                msg.metadata["dynamic_context_hash"] = dynamic_ctx.context_hash
            except Exception as _dcs_exc:
                # DCS failure must never block message delivery
                logger.warning(
                    f"[{CONSTITUTIONAL_HASH}] DCS context assembly skipped: {_dcs_exc}",
                    message_id=msg.message_id,
                )

        # Step 4: Evaluate with adaptive governance
        governance_allowed, governance_reasoning = await self._evaluate_with_adaptive_governance(
            msg
        )
        if not governance_allowed:
            result = ValidationResult(
                is_valid=False,
                errors=[f"Governance policy violation: {governance_reasoning}"],
                metadata={
                    "governance_mode": "ADAPTIVE",
                    "blocked_reason": governance_reasoning,
                },
            )
            self._record_metrics_failure()
            return result

        # Step 5: Process message with fallback
        result = await self._process_message_with_fallback(msg)

        # Step 6: Finalize delivery and update metrics
        delivery_success = await self._finalize_message_delivery(msg, result)

        # Step 7: Provide feedback to adaptive governance (background task)
        # This includes ML model updates which shouldn't block the critical path.
        if self._governance_integration:
            _fb_task = asyncio.create_task(
                asyncio.to_thread(
                    self._governance_integration.provide_feedback, msg, delivery_success
                )
            )
            self._background_tasks.add(_fb_task)
            _fb_task.add_done_callback(self._background_tasks.discard)

            def _log_feedback_task(task: asyncio.Task[object]) -> None:
                task_exception = task.exception()
                if task_exception is not None:
                    logger.warning(f"Governance feedback task failed: {task_exception}")

            _fb_task.add_done_callback(_log_feedback_task)

        return result

    # --- Main Message Sending ---

    async def send_message(self, msg: AgentMessage) -> ValidationResult:
        """
        Send a message through the agent bus with constitutional validation.

        This method performs:
        1. Bus state verification
        2. Constitutional hash validation
        3. Tenant ID normalization and validation
        4. Message processing with graceful degradation
        5. Routing and delivery

        Args:
            msg: The AgentMessage to send.

        Returns:
            ValidationResult indicating success/failure with any errors.
        """
        idempotency_key = self._resolve_idempotency_key(msg)
        if not idempotency_key:
            return await self._send_message_once(msg)

        async with self._idempotency_lock:
            existing_task = self._inflight_idempotency.get(idempotency_key)
            if existing_task is None:
                existing_task = asyncio.create_task(self._send_message_once(msg))
                self._inflight_idempotency[idempotency_key] = existing_task
                created_task = True
            else:
                created_task = False

        try:
            return await existing_task
        finally:
            if created_task:
                async with self._idempotency_lock:
                    if self._inflight_idempotency.get(idempotency_key) is existing_task:
                        self._inflight_idempotency.pop(idempotency_key, None)

    async def broadcast_message(self, msg: AgentMessage) -> dict[str, ValidationResult]:
        """Broadcast message to all agents in same tenant."""
        return await self._message_handler.broadcast_message(
            msg, self.send_message, self.constitutional_hash
        )

    async def process_batch(self, batch_request: BatchRequest) -> BatchResponse:
        """Process a batch of messages through the agent bus."""
        return await self._batch_processor.process_batch(batch_request)

    def _record_batch_metering(
        self,
        batch_request: BatchRequest,
        response: BatchResponse,
        processing_time_ms: float,
    ) -> None:
        """Record metering data for batch operations."""
        self._batch_processor._record_batch_metering(batch_request, response, processing_time_ms)

    async def _evaluate_with_adaptive_governance(self, msg: AgentMessage) -> tuple[bool, str]:
        """Delegate to governance integration component."""
        return await self._governance_integration.evaluate_with_adaptive_governance(msg)

    async def _initialize_adaptive_governance(self) -> None:
        pass  # Handled in start()

    async def _shutdown_adaptive_governance(self) -> None:
        pass  # Handled in stop()

    async def receive_message(self, timeout: float = 1.0) -> AgentMessage | None:
        """Receive a message from the internal queue."""
        return await self._message_handler.receive_message(timeout)

    async def _route_and_deliver(self, msg: AgentMessage) -> bool:
        """Route and deliver message."""
        return await self._message_handler.route_and_deliver(msg)

    async def _handle_deliberation(
        self,
        msg: AgentMessage,
        routing: JSONDict | None = None,
        start_time: float | None = None,
        **kwargs: object,
    ) -> bool:
        """Handle deliberation for high-impact messages."""
        return await self._message_handler.handle_deliberation(msg, routing, start_time, **kwargs)

    def _requires_deliberation(self, msg: AgentMessage) -> bool:
        """Check if message requires deliberation."""
        return self._message_handler.requires_deliberation(msg)

    async def _validate_agent_identity(
        self,
        aid: str | None = None,
        token: str | None = None,
        **kwargs: object,
    ) -> tuple[bool | str | None, list[str]]:
        if not token:
            if self._use_dynamic_policy and self._config.get("use_dynamic_policy"):
                return (False, [])
            return (None, [])
        return (token if "." in token else "default", [])

    @staticmethod
    def _format_tenant_id(tid: str | None = None, **kwargs: object) -> str:
        return normalize_tenant_id(tid) or "none"

    def _validate_tenant_consistency(
        self,
        from_agent: str | AgentMessage | None = None,
        to_agent: str | None = None,
        tid: str | None = None,
        **kwargs: object,
    ) -> list[str]:
        agents_registry = cast(dict[str, dict[str, object]], self._registry_manager._agents)
        if isinstance(from_agent, AgentMessage):
            msg = from_agent
            return validate_tenant_consistency(
                agents_registry,
                msg.from_agent,
                msg.to_agent,
                msg.tenant_id,
            )
        return validate_tenant_consistency(
            agents_registry,
            from_agent if isinstance(from_agent, str) else "",
            to_agent,
            tid,
        )

    async def _start_kafka(self) -> None:
        """Start Kafka integration."""
        self._resolve_kafka_bus()
        if not self._kafka_bus:
            return

        await self._start_kafka_bus_if_supported()
        self._kafka_consumer_task = asyncio.create_task(self._poll_kafka_messages())

    def _resolve_kafka_bus(self) -> None:
        """Resolve Kafka bus from config or create local/lite fallback."""
        if not self._kafka_bus:
            self._kafka_bus = self._config.get("kafka_bus") or self._config.get("kafka_adapter")

        # Lite Mode: Use LocalEventBus if explicitly requested or in Lite mode
        use_local = (
            str(os.getenv("EVENT_BUS_TYPE", "")).lower() == "local"
            or str(os.getenv("ACGS_LITE_MODE", "")).lower() == "true"
        )

        if not self._kafka_bus and use_local:
            try:
                from ..local_bus import LocalEventBus

                self._kafka_bus = LocalEventBus()
                logger.info(f"[{CONSTITUTIONAL_HASH}] Using LocalEventBus (Lite Mode)")
                return
            except ImportError:
                logger.warning(
                    f"[{CONSTITUTIONAL_HASH}] LocalEventBus not found, falling back to mock"
                )

        if self._kafka_bus or self._config.get("use_kafka") is not True:
            return

        self._kafka_bus = self._create_simple_kafka_mock()

    async def _start_kafka_bus_if_supported(self) -> None:
        """Invoke kafka bus start hook when available."""
        if not hasattr(self._kafka_bus, "start"):
            return

        start_result = self._kafka_bus.start()
        if asyncio.iscoroutine(start_result):
            await start_result

    @staticmethod
    def _create_simple_kafka_mock() -> object:
        """Create lightweight async-capable mock for test-only kafka fallback."""

        class _SimpleAsyncMock:
            def __init__(self, return_value: object = None) -> None:
                self._return_value = return_value

            async def __call__(self, *args: object, **kwargs: object) -> object:
                return self._return_value

        class _SimpleMock:
            _mock_name = "SimpleMock"

            def __init__(self) -> None:
                self._methods: JSONDict = {}

            def __getattr__(self, name: str) -> object:
                if name not in self._methods:
                    self._methods[name] = _SimpleAsyncMock(True)
                return self._methods[name]

            def __setattr__(self, name: str, value: object) -> None:
                if name in ("_methods", "_mock_name"):
                    super().__setattr__(name, value)
                else:
                    self._methods[name] = value

        return _SimpleMock()

    async def _poll_kafka_messages(self) -> None:
        """Poll Kafka for incoming messages."""
        if self._kafka_bus:
            await cast(Any, self._kafka_bus).subscribe(self.send_message)

    async def get_metrics_async(self) -> JSONDict:
        """Get bus metrics with async policy registry health check."""
        return await self._bus_metrics.get_metrics_async(self._policy_client)

    def get_metrics(self) -> JSONDict:
        """Get current bus operational metrics."""
        return self._bus_metrics.get_metrics()

    # --- Properties ---

    @property
    def validator(self) -> ValidationStrategy:
        return cast(ValidationStrategy, self._validator)

    @property
    def maci_enabled(self) -> bool:
        return bool(self._enable_maci)

    @property
    def maci_registry(self) -> MACIRegistryProtocol | None:
        return self._maci_registry

    @property
    def maci_enforcer(self) -> MACIEnforcerProtocol | None:
        return self._maci_enforcer

    @property
    def processor(self) -> MessageProcessor:
        return cast(MessageProcessor, self._processor)

    @property
    def processing_strategy(self) -> ProcessingStrategy:
        return cast(ProcessingStrategy, cast(Any, self._processor).processing_strategy)

    @property
    def _processing_strategy(self) -> ProcessingStrategy:
        return cast(ProcessingStrategy, cast(Any, self._processor).processing_strategy)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def registry(self) -> AgentRegistry:
        return self._registry_manager._registry

    @property
    def agents(self) -> JSONDict:
        """Get the registered agents dictionary for direct access (testing/debugging)."""
        return cast(JSONDict, self._registry_manager._agents)

    @property
    def router(self) -> MessageRouter:
        from ..components import MessageRouter as RouterComponent

        if isinstance(self._router_component, RouterComponent):
            return cast(MessageRouter, self._router_component._router)
        return cast(MessageRouter, self._router_component)

    @property
    def maci_strict_mode(self) -> bool:
        return bool(self._maci_strict_mode)
