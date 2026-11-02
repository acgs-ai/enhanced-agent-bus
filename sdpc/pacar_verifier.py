from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

from enhanced_agent_bus.config import BusConfiguration

from .conversation import MessageRole
from .pacar_manager import PACARManager

sys.modules.setdefault("enhanced_agent_bus.sdpc.pacar_verifier", sys.modules[__name__])

# PACAR verdicts are advisory (recorded in result metadata as sdpc_pacar_*; they do not
# change MessageProcessor accept/reject). Even so, the verdict itself must fail closed.
_ACCEPTABLE_RISK_LEVELS = frozenset({"low", "medium"})


def _tenant_scoped_session(tenant_id: str | None, session_id: str) -> str:
    """Session-store key component isolated per tenant.

    Length-prefixing the tenant keeps ("a:b", "c") and ("a", "b:c") distinct, so one tenant
    can never read or append to another tenant's PACAR conversation history.
    """
    tenant = tenant_id or ""
    return f"{len(tenant)}:{tenant}:{session_id}"


class _DefaultAssistant:
    """Placeholder reviewer: no real review is wired, so PACAR must deny.

    PACAR is enforcing. Approving without a review would let every PACAR-routed
    message (all TASK_REQUESTs) through unscreened. Wire a real assistant via
    ``get_llm_assistant`` before relying on PACAR to approve anything.
    """

    async def analyze_message_impact(self, content: str) -> dict[str, Any]:
        _ = content
        return {
            "risk_level": "unreviewed",
            "confidence": 0.0,
            "reasoning": ["no_pacar_reviewer_configured"],
            "mitigations": ["configure_pacar_reviewer"],
        }

    async def ainvoke_multi_turn(
        self, content: str, history: list[dict[str, Any]]
    ) -> dict[str, Any]:
        _ = (content, history)
        return {
            "recommended_decision": "reject",
            "risk_level": "unreviewed",
            "confidence": 0.0,
            "reasoning": ["no_pacar_reviewer_configured"],
            "mitigations": ["configure_pacar_reviewer"],
        }


def get_llm_assistant() -> Any:
    return _DefaultAssistant()


class PACARVerifier:
    def __init__(self, config: BusConfiguration | None = None) -> None:
        self.config = config or BusConfiguration()
        self.assistant = get_llm_assistant()
        self.manager = PACARManager(config=self.config)
        self.redis_client: Any | None = None
        self.audit_client: Any | None = None

    async def verify(self, content: str, original_intent: str) -> dict[str, Any]:
        analysis = await self.assistant.analyze_message_impact(content)
        # Fail closed: only an explicit low/medium risk verdict is valid. A missing,
        # unknown, "high" or "critical" risk_level is invalid.
        risk_ok = analysis.get("risk_level") in _ACCEPTABLE_RISK_LEVELS
        # A reviewer that states a decision must state "approve"; "reject"/"review"/other
        # blocks even when the risk level looks acceptable.
        decision = analysis.get("recommended_decision")
        if decision is not None and decision != "approve":
            risk_ok = False
        return {
            "is_valid": risk_ok,
            "confidence": analysis.get("confidence", 0.0),
            "reasoning": analysis.get("reasoning", []),
            "mitigations": analysis.get("mitigations", []),
            "consensus_reached": risk_ok,
            "critique": analysis.get("reasoning", []),
        }

    async def verify_with_context(
        self,
        content: str,
        original_intent: str,
        session_id: str,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        scoped_session = _tenant_scoped_session(tenant_id, session_id)
        redis_key = f"pacar:session:{scoped_session}"
        conversation: dict[str, Any]
        if self.redis_client is not None:
            existing = await self.redis_client.get(redis_key)
            conversation = (
                json.loads(existing)
                if existing
                else {
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "messages": [],
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
        else:
            state = await self.manager.get_state(scoped_session)
            if hasattr(state, "model_dump") and callable(state.model_dump):
                dumped = state.model_dump()
                conversation = dumped if isinstance(dumped, dict) else {}
            else:
                conversation = {}
            if not conversation:
                conversation = {
                    "session_id": session_id,
                    "tenant_id": tenant_id,
                    "messages": [
                        msg.model_dump() if hasattr(msg, "model_dump") else msg
                        for msg in getattr(state, "messages", [])
                    ],
                }
            conversation.setdefault("tenant_id", tenant_id)

        multi_turn = await self.assistant.ainvoke_multi_turn(
            content, conversation.get("messages", [])
        )
        # Fail closed: a missing or empty decision is treated as "reject", never "approve".
        decision = multi_turn.get("recommended_decision") or "reject"
        verification_result = {
            "is_valid": decision == "approve",
            "confidence": multi_turn.get("confidence", 0.0),
        }
        entry = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
            "intent": original_intent,
            "verification_result": verification_result,
        }
        conversation.setdefault("messages", []).append(entry)
        if len(conversation["messages"]) > 50:
            conversation["messages"] = conversation["messages"][-50:]
        conversation["session_id"] = session_id
        conversation["tenant_id"] = tenant_id  # key is tenant-scoped; never inherit another
        conversation["updated_at"] = datetime.now(UTC).isoformat()

        if self.redis_client is not None:
            await self.redis_client.setex(redis_key, 3600, json.dumps(conversation))

        if self.manager is not None:
            await self.manager.add_message(
                scoped_session, MessageRole.USER, content, {"intent": original_intent}
            )
            await self.manager.add_message(
                scoped_session,
                MessageRole.ASSISTANT,
                "\n".join(multi_turn.get("reasoning", [])),
                {"phase": "critique"},
            )
            await self.manager.add_message(
                scoped_session,
                MessageRole.SYSTEM,
                decision,
                {"phase": "decision"},
            )

        result = {
            "is_valid": verification_result["is_valid"],
            "confidence": verification_result["confidence"],
            "reasoning": multi_turn.get("reasoning", []),
            "mitigations": multi_turn.get("mitigations", []),
            "recommended_decision": decision,
            "consensus_reached": verification_result["is_valid"],
            "session_id": session_id,
            "message_count": len(conversation["messages"]),
        }
        if self.audit_client is not None and hasattr(self.audit_client, "report_decision"):
            await self.audit_client.report_decision(result)
        return result
