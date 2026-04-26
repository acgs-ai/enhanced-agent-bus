"""ACGS-2 Enhanced Agent Communication Bus / Constitutional Hash: 608508a9bd224290"""

CONSTITUTIONAL_HASH = "608508a9bd224290"
__version__ = "3.0.2"
__constitutional_hash__ = "608508a9bd224290"

# Single shared state dict: maps attr names to resolved values.
# Special keys: "\x00lazy" -> _LAZY dict, "\x00ext" -> _ext_exports dict, "\x00flags" -> flags dict
_S = {}


def __getattr__(name):
    if name in _S:
        v = _S[name]
        # skip internal sentinel keys
        if not name.startswith("\x00"):
            return v

    lazy = _S.get("\x00lazy")
    if lazy is None:
        lazy = _S["\x00lazy"] = {
            "EnhancedAgentBus": ("enhanced_agent_bus.agent_bus", None),
            "BusConfiguration": ("enhanced_agent_bus.config", None),
            "_get_feature_flags": ("enhanced_agent_bus.dependency_bridge", "get_feature_flags"),
            "AgentAlreadyRegisteredError": ("enhanced_agent_bus.exceptions", None),
            "AgentBusError": ("enhanced_agent_bus.exceptions", None),
            "AgentCapabilityError": ("enhanced_agent_bus.exceptions", None),
            "AgentError": ("enhanced_agent_bus.exceptions", None),
            "AgentNotRegisteredError": ("enhanced_agent_bus.exceptions", None),
            "BusAlreadyStartedError": ("enhanced_agent_bus.exceptions", None),
            "BusNotStartedError": ("enhanced_agent_bus.exceptions", None),
            "BusOperationError": ("enhanced_agent_bus.exceptions", None),
            "ConfigurationError": ("enhanced_agent_bus.exceptions", None),
            "ConstitutionalError": ("enhanced_agent_bus.exceptions", None),
            "ConstitutionalHashMismatchError": ("enhanced_agent_bus.exceptions", None),
            "ConstitutionalValidationError": ("enhanced_agent_bus.exceptions", None),
            "DeliberationError": ("enhanced_agent_bus.exceptions", None),
            "DeliberationTimeoutError": ("enhanced_agent_bus.exceptions", None),
            "HandlerExecutionError": ("enhanced_agent_bus.exceptions", None),
            "MessageDeliveryError": ("enhanced_agent_bus.exceptions", None),
            "MessageError": ("enhanced_agent_bus.exceptions", None),
            "MessageRoutingError": ("enhanced_agent_bus.exceptions", None),
            "MessageTimeoutError": ("enhanced_agent_bus.exceptions", None),
            "MessageValidationError": ("enhanced_agent_bus.exceptions", None),
            "OPAConnectionError": ("enhanced_agent_bus.exceptions", None),
            "OPANotInitializedError": ("enhanced_agent_bus.exceptions", None),
            "PolicyError": ("enhanced_agent_bus.exceptions", None),
            "PolicyEvaluationError": ("enhanced_agent_bus.exceptions", None),
            "PolicyNotFoundError": ("enhanced_agent_bus.exceptions", None),
            "ReviewConsensusError": ("enhanced_agent_bus.exceptions", None),
            "SignatureCollectionError": ("enhanced_agent_bus.exceptions", None),
            "AgentRegistry": ("enhanced_agent_bus.interfaces", None),
            "MessageHandler": ("enhanced_agent_bus.interfaces", None),
            "MessageRouter": ("enhanced_agent_bus.interfaces", None),
            "MetricsCollector": ("enhanced_agent_bus.interfaces", None),
            "ValidationStrategy": ("enhanced_agent_bus.interfaces", None),
            "MessageProcessor": ("enhanced_agent_bus.message_processor", None),
            "MeteringManager": ("enhanced_agent_bus.metering_manager", None),
            "create_metering_manager": ("enhanced_agent_bus.metering_manager", None),
            "AgentMessage": ("enhanced_agent_bus.models", None),
            "MessageStatus": ("enhanced_agent_bus.models", None),
            "MessageType": ("enhanced_agent_bus.models", None),
            "ModelPQCMetadata": ("enhanced_agent_bus.models", "PQCMetadata"),
            "MODEL_HASH": ("enhanced_agent_bus.models", "CONSTITUTIONAL_HASH"),
            "Priority": ("enhanced_agent_bus.models", None),
            "RiskLevel": ("enhanced_agent_bus.models", None),
            "RoutingContext": ("enhanced_agent_bus.models", None),
            "SessionGovernanceConfig": ("enhanced_agent_bus.models", None),
            "ValidationStatus": ("enhanced_agent_bus.models", None),
            "PolicyResolutionResult": ("enhanced_agent_bus.policy_resolver", None),
            "PolicyResolver": ("enhanced_agent_bus.policy_resolver", None),
            "CapabilityBasedRouter": ("enhanced_agent_bus.registry", None),
            "CompositeValidationStrategy": ("enhanced_agent_bus.registry", None),
            "DirectMessageRouter": ("enhanced_agent_bus.registry", None),
            "DynamicPolicyValidationStrategy": ("enhanced_agent_bus.registry", None),
            "InMemoryAgentRegistry": ("enhanced_agent_bus.registry", None),
            "RedisAgentRegistry": ("enhanced_agent_bus.registry", None),
            "RustValidationStrategy": ("enhanced_agent_bus.registry", None),
            "StaticHashValidationStrategy": ("enhanced_agent_bus.registry", None),
            "RuntimeSecurityConfig": ("enhanced_agent_bus.runtime_security", None),
            "RuntimeSecurityScanner": ("enhanced_agent_bus.runtime_security", None),
            "SecurityEvent": ("enhanced_agent_bus.runtime_security", None),
            "SecurityEventType": ("enhanced_agent_bus.runtime_security", None),
            "SecurityScanResult": ("enhanced_agent_bus.runtime_security", None),
            "SecuritySeverity": ("enhanced_agent_bus.runtime_security", None),
            "get_runtime_security_scanner": ("enhanced_agent_bus.runtime_security", None),
            "scan_content": ("enhanced_agent_bus.runtime_security", None),
            "SessionContext": ("enhanced_agent_bus.session_context", None),
            "SessionContextManager": ("enhanced_agent_bus.session_context", None),
            "SessionContextStore": ("enhanced_agent_bus.session_context", None),
            "AlertLevel": ("enhanced_agent_bus.siem_integration", None),
            "AlertManager": ("enhanced_agent_bus.siem_integration", None),
            "AlertThreshold": ("enhanced_agent_bus.siem_integration", None),
            "EventCorrelator": ("enhanced_agent_bus.siem_integration", None),
            "SIEMConfig": ("enhanced_agent_bus.siem_integration", None),
            "SIEMEventFormatter": ("enhanced_agent_bus.siem_integration", None),
            "SIEMFormat": ("enhanced_agent_bus.siem_integration", None),
            "SIEMIntegration": ("enhanced_agent_bus.siem_integration", None),
            "close_siem": ("enhanced_agent_bus.siem_integration", None),
            "get_siem_integration": ("enhanced_agent_bus.siem_integration", None),
            "initialize_siem": ("enhanced_agent_bus.siem_integration", None),
            "log_security_event": ("enhanced_agent_bus.siem_integration", None),
            "security_audit": ("enhanced_agent_bus.siem_integration", None),
            "ValidationResult": ("enhanced_agent_bus.validators", None),
        }
        _S["\x00ext"] = {}

    if name in ("CIRCUIT_BREAKER_ENABLED", "DELIBERATION_AVAILABLE",
                "METERING_AVAILABLE", "METRICS_ENABLED", "USE_RUST"):
        flags = _S.get("\x00flags")
        if flags is None:
            import importlib
            m = importlib.import_module("enhanced_agent_bus.dependency_bridge")
            flags = _S["\x00flags"] = m.get_feature_flags()
        val = flags.get(name, False)
        _S[name] = val
        return val

    if name == "EnhancedAgentBus" or name == "AgentMessage":
        if name in lazy:
            mod_path, attr = lazy[name]
            _cache = [None]
            def _resolve():
                if _cache[0] is None:
                    import importlib
                    m = importlib.import_module(mod_path)
                    _cache[0] = getattr(m, attr if attr is not None else name)
                return _cache[0]
            class _P:
                def __call__(self, *a, **kw): return _resolve()(*a, **kw)
                def __getattr__(self, n): return getattr(_resolve(), n)
            p = _P()
            _S[name] = p
            return p

    if name in lazy:
        mod_path, attr = lazy[name]
        import importlib
        mod = importlib.import_module(mod_path)
        val = getattr(mod, attr if attr is not None else name)
        _S[name] = val
        return val

    import importlib
    ext = _S["\x00ext"]
    for mp in (
        "enhanced_agent_bus._ext_cache_warming",
        "enhanced_agent_bus._ext_chaos",
        "enhanced_agent_bus._ext_circuit_breaker",
        "enhanced_agent_bus._ext_circuit_breaker_clients",
        "enhanced_agent_bus._ext_cognitive",
        "enhanced_agent_bus._ext_context_memory",
        "enhanced_agent_bus._ext_context_optimization",
        "enhanced_agent_bus._ext_decision_store",
        "enhanced_agent_bus._ext_explanation_service",
        "enhanced_agent_bus._ext_langgraph",
        "enhanced_agent_bus._ext_mcp",
        "enhanced_agent_bus._ext_performance",
        "enhanced_agent_bus._ext_persistence",
        "enhanced_agent_bus._ext_pqc",
        "enhanced_agent_bus._ext_response_quality",
    ):
        if mp not in ext:
            try:
                mod = importlib.import_module(mp)
                exported = getattr(mod, "_EXT_ALL", None)
                if exported is None:
                    exported = [n for n in dir(mod) if not n.startswith("_")]
                ext[mp] = set(exported)
                for n in exported:
                    if n not in _S:
                        v = getattr(mod, n, None)
                        if v is not None:
                            _S[n] = v
            except Exception:
                ext[mp] = set()
        if name in ext[mp]:
            return _S.get(name)

    raise AttributeError(f"module 'enhanced_agent_bus' has no attribute {name!r}")
