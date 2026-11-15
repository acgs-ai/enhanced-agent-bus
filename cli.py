"""Command line entry point for enhanced-agent-bus (``eab``).

Commands:

* ``eab version``: print the package version.
* ``eab check <message-json | ->``: validate the input with the API's own
  ``MessageRequest`` model, build the ``AgentMessage`` with the API's own
  ``_build_agent_message`` (api/routes/messages.py), run it through
  ``MessageProcessor.process`` (the call the HTTP API makes for
  ``POST /api/v1/messages``) and print the decision.

``eab check`` makes no network calls and writes no files of its own (the
interpreter and litellm create and delete a temp-dir probe file at import).
It builds the processor with ``isolated_mode=True``: the API's authentication,
tenant binding, MACI, OPA, dynamic policy, Rust/composite strategies, session
governance and the other gates listed in ``SKIPPED_GATES`` are NOT evaluated, and
the verdict depends on environment flags (reported under ``flags``). The decision
is therefore ``ALLOW_ISOLATED`` / ``DENY_ISOLATED``, never a production approval.

Input is a ``MessageRequest`` JSON object (content, sender, ...), at most
``MAX_INPUT_BYTES`` bytes, with no duplicate keys and no NaN/Infinity.

Exit codes: 0 allowed, 1 denied, 2 validation could not run (bad input,
internal error). Nothing but an explicit ALLOW from the processor exits 0.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from importlib import metadata
from typing import Any

EXIT_ALLOW = 0
EXIT_DENY = 1
EXIT_ERROR = 2

# MessageRequest.content allows 1 MiB; 2 MiB leaves room for the other fields.
MAX_INPUT_BYTES = 2 * 1024 * 1024

_DISTRIBUTION = "enhanced-agent-bus"

SKIPPED_GATES = (
    "authentication (JWT / UserClaims)",
    "tenant binding to an authenticated tenant (tenant_id comes from the input, default 'default')",
    "rate limiting and independent-validator request headers",
    "MACI role enforcement",
    "OPA and dynamic policy",
    "Rust processing strategy",
    "composite processing strategy",
    "session governance",
    "metering",
    "audit client, workflow persistence and dead-letter queue",
)


class CheckError(Exception):
    """Validation could not run; the message must be treated as not allowed."""


def _package_version() -> str:
    try:
        return metadata.version(_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        from enhanced_agent_bus import __version__

        return str(__version__)


def _read_message_text(source: str) -> str:
    try:
        if source == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with open(source, "rb") as handle:
                raw = handle.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise CheckError(f"cannot read message from {source!r}: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise CheckError(f"input exceeds the {MAX_INPUT_BYTES}-byte limit")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError(f"input is not valid UTF-8: {exc}") from exc


def _reject_constant(name: str) -> Any:
    raise CheckError(f"non-finite number {name} is not allowed")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _parse_message_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise CheckError(f"message is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CheckError("message JSON must be an object")
    return data


def _require_finite(value: object, where: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise CheckError(f"non-finite number in {where}")
    if isinstance(value, dict):
        for item in value.values():
            _require_finite(item, where)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_finite(item, where)


def _read_only_processor_class() -> type:
    """Return a MessageProcessor subclass whose dead-letter queue sink is inert."""
    from enhanced_agent_bus.message_processor import MessageProcessor

    class _NullDlq:
        """Inert stand-in for the Redis dead-letter queue: nothing is written."""

        async def lpush(self, *args: object, **kwargs: object) -> int:
            return 0

        async def ltrim(self, *args: object, **kwargs: object) -> bool:
            return True

    class _ReadOnlyProcessor(MessageProcessor):
        # Rejections are normally pushed to a Redis DLQ after the decision is made.
        # Only that sink is replaced; every gate runs unchanged.
        async def _get_dlq_redis(self) -> object:
            return _NullDlq()

    return _ReadOnlyProcessor


async def _validate(data: dict[str, Any]) -> dict[str, Any]:
    # Offline guarantees: no LiteLLM Redis cache connection, and no download of
    # LiteLLM's model-cost map when litellm is imported (it uses its bundled copy).
    os.environ["LLM_USE_CACHE"] = "false"
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

    # message_processor must be imported before the api package (circular import
    # otherwise), so keep this order.
    # isort: off
    import enhanced_agent_bus.message_processor  # noqa: F401
    from enhanced_agent_bus.api.routes import messages as api_messages
    from enhanced_agent_bus.api_models import MessageRequest
    from pydantic import ValidationError

    # isort: on

    try:
        request = MessageRequest.model_validate(data)
    except ValidationError as exc:
        raise CheckError(f"input is not a valid MessageRequest: {exc}") from exc

    # Same construction as the API's send_message handler, minus authentication:
    # the tenant comes from the input because there is no authenticated user.
    tenant_id = request.tenant_id or "default"
    message = api_messages._build_agent_message(
        request,
        api_messages._merge_validator_headers_into_metadata(request, None, None, None),
        tenant_id,
        api_messages._resolve_message_type(request.message_type),
        api_messages._resolve_priority(request.priority),
        api_messages._resolve_session_id(None, request),
    )
    _require_finite(message.metadata, "metadata")
    _require_finite(message.payload, "payload")
    if message.impact_score is not None and not math.isfinite(message.impact_score):
        raise CheckError("impact_score must be a finite number")

    processor = _read_only_processor_class()(isolated_mode=True)
    flags = {
        "eab_profile": os.getenv("EAB_PROFILE"),
        "require_independent_validator": processor._require_independent_validator,
        "independent_validator_threshold": processor._independent_validator_threshold,
        "governance_core_mode": processor._governance_core_mode,
        "enable_pqc": processor._enable_pqc,
    }
    try:
        result = await processor.process(message)
    finally:
        await processor.shutdown()

    metadata_ = result.metadata if isinstance(result.metadata, dict) else {}
    reason = metadata_.get("rejection_reason")
    if reason == "max_retries_exceeded":
        raise CheckError("; ".join(str(e) for e in result.errors) or "processing failed")

    # ValidationResult.decision defaults to "ALLOW" even when is_valid is False,
    # so ALLOW requires both fields to agree.
    allowed = result.is_valid is True and str(result.decision).upper() == "ALLOW"
    return {
        "decision": "ALLOW_ISOLATED" if allowed else "DENY_ISOLATED",
        "mode": "isolated",
        "is_valid": result.is_valid,
        "message_id": message.message_id,
        "errors": [str(e) for e in result.errors],
        "warnings": [str(w) for w in result.warnings],
        "rejection_reason": reason,
        "constitutional_hash": result.constitutional_hash,
        "flags": flags,
        "skipped_gates": list(SKIPPED_GATES),
    }


def _cmd_check(source: str) -> int:
    try:
        data = _parse_message_json(_read_message_text(source))
        report = asyncio.run(_validate(data))
    except CheckError as exc:
        print(f"eab check: cannot validate: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # fail closed: an internal error is never an ALLOW
        print(f"eab check: validation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(json.dumps(report, indent=2, default=str))
    return EXIT_ALLOW if report["decision"] == "ALLOW_ISOLATED" else EXIT_DENY


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eab", description="Enhanced Agent Bus command line.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the package version")
    check = sub.add_parser(
        "check",
        help="validate one MessageRequest (offline, isolated gates only); "
        "exit 0 allow, 1 deny, 2 cannot validate",
    )
    check.add_argument("message", help="path to a MessageRequest JSON file, or - for stdin")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "version":
        print(_package_version())
        return EXIT_ALLOW
    return _cmd_check(args.message)


if __name__ == "__main__":
    sys.exit(main())
