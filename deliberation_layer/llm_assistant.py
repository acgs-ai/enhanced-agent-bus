"""
Constitutional Hash: 608508a9bd224290
"""

import time
from enum import Enum
from typing import Any, Protocol, cast

from enhanced_agent_bus.bus_types import JSONDict, JSONValue
from enhanced_agent_bus.observability.structured_logging import get_logger

try:
    from enhanced_agent_bus.models import (
        CONSTITUTIONAL_HASH as _ConstitutionalHashImport,
    )
    from enhanced_agent_bus.models import (
        AgentMessage as _AgentMessageImport,
    )
    from enhanced_agent_bus.models import (
        MessageType as _MessageTypeImport,
    )
    from enhanced_agent_bus.models import (
        get_enum_value as _GetEnumValueImport,
    )
    from enhanced_agent_bus.utils import get_iso_timestamp as _GetIsoTimestampImport

    _ConstitutionalHash: Any = _ConstitutionalHashImport
    _AgentMessage: Any = _AgentMessageImport
    _MessageType: Any = _MessageTypeImport
    _GetEnumValue: Any = _GetEnumValueImport
    _GetIsoTimestamp: Any = _GetIsoTimestampImport
except ImportError:
    try:
        from ..models import (
            CONSTITUTIONAL_HASH as _ConstitutionalHashImport,
        )
        from ..models import (
            AgentMessage as _AgentMessageImport,
        )
        from ..models import (
            MessageType as _MessageTypeImport,
        )
        from ..models import (
            get_enum_value as _GetEnumValueImport,
        )
        from ..utils import get_iso_timestamp as _GetIsoTimestampImport

        _ConstitutionalHash = _ConstitutionalHashImport
        _AgentMessage = _AgentMessageImport
        _MessageType = _MessageTypeImport
        _GetEnumValue = _GetEnumValueImport
        _GetIsoTimestamp = _GetIsoTimestampImport
    except ImportError:
        _ConstitutionalHash = "standalone"
        _AgentMessage = cast(Any, object)
        _MessageType = cast(Any, object)

        def _GetEnumValue(enum_or_str: Enum | str) -> str:
            return str(enum_or_str)

        def _GetIsoTimestamp() -> str:
            from datetime import UTC, datetime

            return datetime.now(UTC).isoformat()


CONSTITUTIONAL_HASH = _ConstitutionalHash
AgentMessage = _AgentMessage
MessageType = _MessageType
get_enum_value = _GetEnumValue
get_iso_timestamp = _GetIsoTimestamp


class _AgentMessageLike(Protocol):
    message_id: str
    message_type: Any
    from_agent: str
    to_agent: str
    content: object
    payload: object


logger = get_logger(__name__)
_LLM_ASSISTANT_OPERATION_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    LookupError,
    OSError,
    TimeoutError,
    ConnectionError,
)


def _load_metrics_registry() -> Any | None:
    try:
        from enhanced_agent_bus.observability.telemetry import MetricsRegistry

        return MetricsRegistry
    except ImportError:
        try:
            from ..observability.telemetry import MetricsRegistry

            return MetricsRegistry
        except (ImportError, ValueError):
            return None


MetricsRegistry = _load_metrics_registry()

# Mock classes for test friendliness when LangChain is missing
try:
    from langchain_core.output_parsers import JsonOutputParser as _JsonOutputParserImport
    from langchain_core.prompts import (
        ChatPromptTemplate as _ChatPromptTemplateImport,
    )
    from langchain_core.prompts import (
        HumanMessagePromptTemplate as _HumanMessagePromptTemplateImport,
    )
    from langchain_core.prompts import (
        SystemMessagePromptTemplate as _SystemMessagePromptTemplateImport,
    )
    from langchain_openai import ChatOpenAI as _ChatOpenAIImport

    LANGCHAIN_AVAILABLE = True
    _ChatPromptTemplate: Any = _ChatPromptTemplateImport
    _SystemMessagePromptTemplate: Any = _SystemMessagePromptTemplateImport
    _HumanMessagePromptTemplate: Any = _HumanMessagePromptTemplateImport
    _JsonOutputParser: Any = _JsonOutputParserImport
    _ChatOpenAI: Any = _ChatOpenAIImport
except ImportError:
    LANGCHAIN_AVAILABLE = False
    from unittest.mock import MagicMock

    # Mock classes for test friendliness when LangChain is missing
    class _FallbackChatPromptTemplate:
        @classmethod
        def from_template(cls, template: str) -> Any:
            mock = MagicMock()
            mock.format_messages.return_value = []
            return mock

    class _FallbackSystemMessagePromptTemplate:
        pass

    class _FallbackHumanMessagePromptTemplate:
        pass

    class _FallbackJsonOutputParser:
        def parse(self, text: str) -> JSONDict:
            return {}

    class _FallbackChatOpenAI:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def ainvoke(self, *args: object, **kwargs: object) -> Any:
            mock = MagicMock()
            mock.content = "{}"
            return mock

    _ChatPromptTemplate = _FallbackChatPromptTemplate
    _SystemMessagePromptTemplate = _FallbackSystemMessagePromptTemplate
    _HumanMessagePromptTemplate = _FallbackHumanMessagePromptTemplate
    _JsonOutputParser = _FallbackJsonOutputParser
    _ChatOpenAI = _FallbackChatOpenAI

ChatPromptTemplate: Any = cast(Any, _ChatPromptTemplate)
SystemMessagePromptTemplate: Any = cast(Any, _SystemMessagePromptTemplate)
HumanMessagePromptTemplate: Any = cast(Any, _HumanMessagePromptTemplate)
JsonOutputParser: Any = cast(Any, _JsonOutputParser)
ChatOpenAI: Any = cast(Any, _ChatOpenAI)


class LLMAssistant:
    """LLM-powered assistant for deliberation decision support."""

    def __init__(self, api_key: str | None = None, model_name: str = "gpt-5.5") -> None:
        self.model_name = model_name
        self.llm: Any | None = None
        if LANGCHAIN_AVAILABLE:
            try:
                self.llm = ChatOpenAI(
                    model_name=model_name, temperature=0.1, openai_api_key=api_key
                )
            except _LLM_ASSISTANT_OPERATION_ERRORS as e:
                logger.warning(f"LLM init failed: {e}")

    async def _invoke_llm(self, prompt_tmpl: str, **kwargs: JSONValue) -> JSONDict:
        if not self.llm:
            return {}

        metrics_registry = (
            MetricsRegistry(service_name="llm-assistant") if MetricsRegistry is not None else None
        )

        start_time = time.time()
        try:
            prompt = ChatPromptTemplate.from_template(prompt_tmpl)
            resp = await self.llm.ainvoke(
                prompt.format_messages(**kwargs, constitutional_hash=CONSTITUTIONAL_HASH)
            )
            latency_ms = (time.time() - start_time) * 1000

            # Record latency
            if metrics_registry:
                metrics_registry.record_latency(
                    "llm_invocation_latency", latency_ms, {"model": self.model_name}
                )

            # Track tokens if available (LangChain ChatOpenAI response_metadata)
            token_usage = {}
            if hasattr(resp, "response_metadata") and "token_usage" in resp.response_metadata:
                usage = resp.response_metadata["token_usage"]
                token_usage = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                }
                if metrics_registry:
                    metrics_registry.increment_counter(
                        "llm_tokens_total", token_usage["total_tokens"], {"model": self.model_name}
                    )
                    metrics_registry.increment_counter(
                        "llm_tokens_prompt",
                        token_usage["prompt_tokens"],
                        {"model": self.model_name},
                    )
                    metrics_registry.increment_counter(
                        "llm_tokens_completion",
                        token_usage["completion_tokens"],
                        {"model": self.model_name},
                    )

            result = JsonOutputParser().parse(resp.content)
            if isinstance(result, dict):
                result["_metrics"] = {"latency_ms": latency_ms, "token_usage": token_usage}
                return cast(JSONDict, result)
            return {}
        except _LLM_ASSISTANT_OPERATION_ERRORS as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"LLM invoke failed after {latency_ms:.2f}ms: {e}")
            if metrics_registry:
                metrics_registry.increment_counter(
                    "llm_invocation_failure", 1, {"model": self.model_name, "error": str(type(e))}
                )
            return {}

    async def ainvoke_multi_turn(self, sys_prompt: str, messages: list[dict[str, str]]) -> JSONDict:
        """Invoke LLM with a list of messages for multi-turn support."""
        if not self.llm:
            return {}
        try:
            # Simple implementation for multi-turn
            formatted_msgs = [f"System: {sys_prompt}"]
            for msg in messages:
                formatted_msgs.append(f"{msg['role'].capitalize()}: {msg['content']}")

            prompt_text = "\n".join(formatted_msgs) + "\n\nReturn JSON with the analysis result."

            # Use _invoke_llm with the full prompt text as template (since it's already formatted)
            return await self._invoke_llm(prompt_text)
        except _LLM_ASSISTANT_OPERATION_ERRORS as e:
            logger.error(f"LLM multi-turn invoke failed: {e}")
            return {}

    async def analyze_message_impact(self, message: _AgentMessageLike) -> JSONDict:
        if not self.llm:
            return self._fallback_analysis(message)
        template = """
        CONSTITUTIONAL CONSTRAINT: All analysis must validate against hash {constitutional_hash}

        Security Analysis: Evaluate the message from {from_agent} to {to_agent} for security risks.
        Performance Analysis: Assess if this message impacts system performance.
        Compliance Analysis: Verify compliance with the current constitutional policies.

        Content: {content}
        Message type: {message_type}

        Identify risk_level, recommended_decision, and suggested mitigations.
        Return JSON with: risk_level, requires_human_review, recommended_decision, confidence, reasoning, impact_areas, mitigations, constitutional_hash
        """
        res = await self._invoke_llm(
            template,
            from_agent=message.from_agent,
            to_agent=message.to_agent,
            content=str(message.content)[:500],
            message_type=str(
                message.message_type.value
                if hasattr(message.message_type, "value")
                else message.message_type
            ),
        )
        if not res:
            return self._fallback_analysis(message)
        res.update(
            {
                "analyzed_by": "llm_analyzer",
                "timestamp": get_iso_timestamp(),
                "message_id": message.message_id,
            }
        )
        return res

    async def generate_decision_reasoning(
        self,
        message: _AgentMessageLike,
        votes: list[JSONDict],
        human_decision: str | None = None,
    ) -> JSONDict:
        if not self.llm:
            return self._fallback_reasoning(message, votes, human_decision)
        template = """
        **Action Under Review:** {message_type}

        DELIBERATION CONTEXT
        Review the following votes for action {message_id} to recipient {recipient}.
        Votes: {votes}
        Human Input: {human_decision}

        CONSTITUTIONAL CONSTRAINT: Hash {constitutional_hash} must be validated

        Return JSON with: process_summary, consensus_analysis, final_recommendation, reasoning, concerns, follow_up_actions, constitutional_hash
        """
        res = await self._invoke_llm(
            template,
            message_type=str(
                message.message_type.value
                if hasattr(message.message_type, "value")
                else message.message_type
            ),
            message_id=message.message_id,
            recipient=message.to_agent,
            votes=str(votes)[:500],
            human_decision=human_decision or "None",
        )
        if not res:
            return self._fallback_reasoning(message, votes, human_decision)
        res.update({"generated_by": "llm_reasoner", "timestamp": get_iso_timestamp()})
        return res

    async def analyze_deliberation_trends(self, history: list[JSONDict]) -> JSONDict:
        return self._fallback_analysis_trends(history)

    def _fallback_analysis_trends(self, history: list[JSONDict]) -> JSONDict:
        if not history:
            return {
                "patterns": [],
                "threshold_recommendations": "Maintain current threshold",
                "risk_trends": "stable",
            }

        approved = sum(1 for h in history if h.get("outcome") == "approved")
        total = len(history)
        rate = approved / total if total > 0 else 0

        rec = "Maintain current threshold"
        if rate > 0.8:
            rec = "Systematic high approval observed. Consider lowering deliberation threshold for efficiency."
        elif rate < 0.4:
            rec = "High rejection rate observed. Consider raising deliberation threshold or updating policies."

        return {
            "patterns": [f"Approval rate: {rate:.1%}"],
            "threshold_recommendations": rec,
            "risk_trends": "improving" if rate > 0.6 else "stable",
        }

    def _fallback_analysis(self, message: _AgentMessageLike) -> JSONDict:
        text = str(message.content).lower()
        risk = "low"
        if "breach" in text:
            risk = "critical"
        elif any(k in text for k in ["emergency", "critical", "security", "violation"]):
            risk = "high"

        rev = risk in ["critical", "high"]
        return {
            "risk_level": risk,
            "requires_human_review": rev,
            "recommended_decision": "review" if rev else "approve",
            "confidence": 0.5,
            "reasoning": ["Fallback rule-based analysis"],
            "impact_areas": {"security": "Medium" if "security" in text else "Low"},
            "mitigations": ["Monitor execution"],
            "analyzed_by": "enhanced_fallback_analyzer",
            "timestamp": get_iso_timestamp(),
            "constitutional_hash": CONSTITUTIONAL_HASH,
        }

    def _fallback_reasoning(
        self, message: _AgentMessageLike, votes: list[JSONDict], human_decision: str | None
    ) -> JSONDict:
        app = sum(1 for v in votes if str(v.get("vote")).lower() == "approve")
        total = len(votes)
        rate = app / total if total > 0 else 0
        final = (
            human_decision.lower() if human_decision else ("approve" if rate >= 0.6 else "review")
        )
        return {
            "process_summary": f"Fallback deliberation: {app}/{total} approved",
            "consensus_analysis": f"Strength: {rate:.1%}",
            "final_recommendation": final,
            "reasoning": "Fallback vote synthesis",
            "concerns": [],
            "follow_up_actions": ["Monitor"],
            "generated_by": "enhanced_fallback_reasoner",
            "timestamp": get_iso_timestamp(),
            "constitutional_hash": CONSTITUTIONAL_HASH,
        }

    def _extract_message_summary(self, message: _AgentMessageLike) -> str:
        content_str = str(message.content)
        if len(content_str) > 500:
            content_str = content_str[:497] + "..."
        summary = [
            f"Message ID: {message.message_id}",
            f"type: {message.message_type.value}",
            f"From Agent: {message.from_agent}",
            f"To Agent: {message.to_agent}",
            f"Content: {content_str}",
        ]
        if message.payload:
            payload_str = str(message.payload)
            if len(payload_str) > 200:
                payload_str = payload_str[:197] + "..."
            summary.append(f"Payload: {payload_str}")
        return "\n".join(summary)

    def _summarize_votes(self, votes: list[JSONDict]) -> str:
        if not votes:
            return "No votes recorded"
        total = len(votes)
        approvals = sum(1 for v in votes if v.get("vote") == "approve")
        rejections = sum(1 for v in votes if v.get("vote") == "reject")

        summary = [
            f"Total votes: {total}",
            f"Approve: {approvals}",
            f"Reject: {rejections}",
            "Sample reasoning:",
        ]
        for v in votes[:3]:
            # Handle list or dict for votes
            if isinstance(v, dict):
                v_type = v.get("vote", "unknown")
                reason = v.get("reasoning", "No reasoning provided")
            else:
                v_type = "unknown"
                reason = str(v)
            reason = str(reason)
            if len(reason) > 100:
                reason = reason[:97] + "..."
            summary.append(f"- {v_type}: {reason}")
        return "\n".join(summary)

    def _summarize_deliberation_history(self, history: list[JSONDict]) -> str:
        if not history:
            return "No deliberation history available"
        total = len(history)
        approved = sum(1 for h in history if h.get("outcome") == "approved")
        rejected = sum(1 for h in history if h.get("outcome") == "rejected")
        timed_out = sum(1 for h in history if h.get("outcome") == "timed_out")
        impact_sum = 0.0
        for entry in history:
            raw_impact = entry.get("impact_score", 0.0)
            impact_sum += float(raw_impact) if isinstance(raw_impact, (int, float, str)) else 0.0
        avg_impact = impact_sum / total

        return (
            f"Total deliberations: {total}\n"
            f"Approved: {approved}\n"
            f"Rejected: {rejected}\n"
            f"Timed out: {timed_out}\n"
            f"Average impact score: {avg_impact:.2f}"
        )


_llm_assistant: LLMAssistant | None = None


def get_llm_assistant(**kwargs: object) -> LLMAssistant:
    global _llm_assistant
    if not _llm_assistant:
        _llm_assistant = LLMAssistant(**cast(dict[str, Any], kwargs))
    return _llm_assistant


def reset_llm_assistant() -> None:
    global _llm_assistant
    _llm_assistant = None


__all__ = [
    "ChatPromptTemplate",
    "HumanMessagePromptTemplate",
    "JsonOutputParser",
    "LLMAssistant",
    "SystemMessagePromptTemplate",
    "get_llm_assistant",
    "reset_llm_assistant",
]
