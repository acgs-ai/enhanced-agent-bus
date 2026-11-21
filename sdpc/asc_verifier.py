from __future__ import annotations

from typing import Any

from enhanced_agent_bus.deliberation_layer.intent_classifier import IntentType

_ACCEPTABLE_RISK_LEVELS = frozenset({"low", "medium"})


class _DefaultAssistant:
    """Placeholder reviewer: no real review is wired, so ASC must not report valid."""

    async def analyze_message_impact(self, content: str) -> dict[str, Any]:
        _ = content
        return {
            "risk_level": "unreviewed",
            "confidence": 0.0,
            "reasoning": ["no_asc_reviewer_configured"],
        }


class ASCVerifier:
    def __init__(self) -> None:
        self.assistant: Any = _DefaultAssistant()

    async def verify(self, content: str, intent: IntentType) -> dict[str, Any]:
        if intent is not IntentType.FACTUAL:
            return {"is_valid": True, "reason": "skipped for non-factual intent", "confidence": 1.0}
        result = await self.assistant.analyze_message_impact(content)
        return {
            # Fail closed: only an explicit low/medium risk verdict is valid.
            "is_valid": result.get("risk_level") in _ACCEPTABLE_RISK_LEVELS,
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", []),
        }
