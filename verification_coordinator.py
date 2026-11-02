from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Any, TypeAlias, cast

if TYPE_CHECKING:
    from enhanced_agent_bus._compat.types import JSONDict
else:
    JSONDict: TypeAlias = dict[str, Any]

from .message_processor_components import (
    apply_latency_metadata,
    extract_pqc_failure_result,
    merge_verification_metadata,
    prepare_message_content_string,
)
from .models import AgentMessage
from .processing_context import MessageProcessingContext
from .validators import ValidationResult


class VerificationCoordinator:
    """Encapsulates verification orchestration plus strategy execution."""

    def __init__(
        self,
        *,
        verification_orchestrator: Any,
        processing_strategy: Any,
        handlers: JSONDict,
        attach_governance_metadata: Callable[[MessageProcessingContext, ValidationResult], None],
        increment_failed_count: Callable[[], None],
        handle_successful_processing: Callable[
            [AgentMessage, ValidationResult, str, float], Awaitable[None]
        ],
        handle_failed_processing: Callable[..., Coroutine[object, object, None]],
    ) -> None:
        self._verification_orchestrator = verification_orchestrator
        self._processing_strategy = processing_strategy
        self._handlers = handlers
        self._attach_governance_metadata = attach_governance_metadata
        self._increment_failed_count = increment_failed_count
        self._handle_successful_processing = handle_successful_processing
        self._handle_failed_processing = handle_failed_processing

    def sync_runtime(
        self,
        *,
        verification_orchestrator: Any,
        processing_strategy: Any,
        handlers: JSONDict,
        attach_governance_metadata: Callable[[MessageProcessingContext, ValidationResult], None],
        handle_successful_processing: Callable[
            [AgentMessage, ValidationResult, str, float], Awaitable[None]
        ],
        handle_failed_processing: Callable[..., Coroutine[object, object, None]],
    ) -> None:
        self._verification_orchestrator = verification_orchestrator
        self._processing_strategy = processing_strategy
        self._handlers = handlers
        self._attach_governance_metadata = attach_governance_metadata
        self._handle_successful_processing = handle_successful_processing
        self._handle_failed_processing = handle_failed_processing

    async def perform_sdpc_verification(
        self,
        msg: AgentMessage,
        content_str: str,
    ) -> tuple[JSONDict, JSONDict]:
        return cast(
            tuple[JSONDict, JSONDict],
            await self._verification_orchestrator._perform_sdpc(msg, content_str),
        )

    async def perform_pqc_validation(
        self,
        msg: AgentMessage,
        sdpc_metadata: JSONDict,
    ) -> ValidationResult | None:
        pqc_result, pqc_metadata = await self._verification_orchestrator.verify_pqc(msg)
        if pqc_metadata:
            sdpc_metadata.update(pqc_metadata)
        if pqc_result:
            self._increment_failed_count()
        return cast(ValidationResult | None, pqc_result)

    async def execute(self, context: MessageProcessingContext) -> ValidationResult:
        msg = context.message
        content_str = prepare_message_content_string(msg)
        verification_result = await self._verification_orchestrator.verify(msg, content_str)

        sdpc_metadata = merge_verification_metadata(
            verification_result.sdpc_metadata,
            verification_result.pqc_metadata,
        )

        pqc_failure_result = extract_pqc_failure_result(verification_result)
        if pqc_failure_result:
            self._increment_failed_count()
            self._attach_governance_metadata(context, pqc_failure_result)
            await self._handle_failed_processing(
                msg,
                pqc_failure_result,
                increment_failed_count=False,
                failure_stage="verification",
            )
            return pqc_failure_result

        # PACAR is enforcing: when PACAR ran (key present), anything but an explicit True
        # rejects before any handler runs. Absence means PACAR was not routed.
        if "sdpc_pacar_valid" in sdpc_metadata and sdpc_metadata["sdpc_pacar_valid"] is not True:
            self._increment_failed_count()
            pacar_failure = ValidationResult(
                is_valid=False,
                errors=["PACAR verification rejected message"],
                metadata={**sdpc_metadata, "rejection_reason": "pacar_verification_failed"},
                decision="DENY",
            )
            self._attach_governance_metadata(context, pacar_failure)
            await self._handle_failed_processing(
                msg,
                pacar_failure,
                increment_failed_count=False,
                failure_stage="verification",
            )
            return pacar_failure

        res = await self._processing_strategy.process(msg, self._handlers)
        res.metadata.update(sdpc_metadata)
        self._attach_governance_metadata(context, res)

        latency_ms = (time.perf_counter() - context.start_time) * 1000
        apply_latency_metadata(res, latency_ms)

        if res.is_valid:
            if context.cache_key is None:
                raise ValueError("Processing context cache_key must be set before execution")
            await self._handle_successful_processing(
                msg,
                res,
                context.cache_key,
                latency_ms,
            )
        else:
            await self._handle_failed_processing(msg, res, failure_stage="strategy")

        return res
