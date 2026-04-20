"""Federated Judge Anchor (fFJA). t-of-N threshold-signed extension of FJA. Constitutional Hash: 608508a9bd224290."""

from __future__ import annotations

import hashlib
import secrets
import weakref
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from enhanced_agent_bus.deliberation_layer.frozen_judge_anchor import (
    FJACandidate,
    FJADecisionReason,
    FJAQuorumResult,
    FrozenJudgeAnchorProtocol,
    FrozenJudgeQuorum,
)
from enhanced_agent_bus.maci_imports import CONSTITUTIONAL_HASH
from enhanced_agent_bus.payload_integrity import _canonicalize_payload

logger = structlog.get_logger(__name__)


# Domain-separation tag for fFJA judge-vote signatures.  Prevents cross-
# subsystem replay against any other Ed25519-signed canonical-JSON payload
# that happens to reuse one of the judge keys.  Bump the `-v<n>` suffix on
# any breaking change to the signed payload schema.
_FFJA_VOTE_DOMAIN_TAG: bytes = b"ACGS-fFJA-vote-v2\x00"

# Full 256-bit sha256 hex of the empty string.  Used when a judge has no
# winner (BELOW_THRESHOLD, EMBEDDER_ERROR, etc.).  Full-width (vs. truncated)
# to resist targeted 64-bit collision attacks on winner_text_hash.
_NO_WINNER_TEXT_HASH: str = hashlib.sha256(b"").hexdigest()

_canonical_json = _canonicalize_payload


def _log_judge_exception(event: str, judge_id: str, exc: Exception) -> None:
    """Log judge-scoped exceptions without leaking exception messages."""
    logger.warning(event, judge_id=judge_id, exc_type=type(exc).__name__)


# =============================================================================
# Value types
# =============================================================================


@dataclass(frozen=True)
class JudgeMember:
    """One federated judge node: (judge_id, public_key, anchor)."""

    judge_id: str
    public_key: bytes
    anchor: FrozenJudgeAnchorProtocol


@dataclass(frozen=True)
class JudgeSignature:
    """One judge's signed vote on its local quorum outcome."""

    judge_id: str
    winner_agent_id: str | None
    winner_text_hash: str
    reason: FJADecisionReason
    signature: bytes


@dataclass(frozen=True)
class _VoteContext:
    """Per-judge vote/signing context shared across local decision and verification."""

    judge_id: str
    session_id: str
    candidates_digest: str
    constitutional_hash: str
    winner_agent_id: str | None = None
    winner_text_hash: str = _NO_WINNER_TEXT_HASH
    reason: FJADecisionReason = FJADecisionReason.EMBEDDER_ERROR
    anchor: FrozenJudgeAnchorProtocol | None = field(default=None, repr=False, compare=False)
    candidates: Sequence[FJACandidate] = field(default_factory=tuple, repr=False, compare=False)
    private_key_bytes: bytes = field(default=b"", repr=False, compare=False)


@dataclass(frozen=True)
class FederatedQuorumResult:
    """Threshold-signed aggregate of N local FJA quorum results.

    ``session_id`` and ``candidates_digest`` bind every judge signature to the
    specific adjudication it was produced for: a signature captured in one
    adjudication cannot be replayed into another one whose candidate set or
    session nonce differs.  Both fields MUST be preserved by any audit or
    replication layer or ``verify_federated_result`` will reject the result.
    """

    agreed: bool
    threshold: int
    num_judges: int
    winner_agent_id: str | None
    winner_text: str | None
    judge_signatures: list[JudgeSignature] = field(default_factory=list)
    dissenting_judges: list[str] = field(default_factory=list)
    constitutional_hash: str = CONSTITUTIONAL_HASH
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    session_id: str = field(default_factory=lambda: secrets.token_hex(16))
    candidates_digest: str = _NO_WINNER_TEXT_HASH

    def to_audit_dict(self) -> dict[str, Any]:
        """Flat audit dict. json.dumps-safe (signatures hex-encoded)."""
        return {
            "agreed": self.agreed,
            "threshold": self.threshold,
            "num_judges": self.num_judges,
            "winner_agent_id": self.winner_agent_id,
            "winner_text": self.winner_text,
            "judge_signatures": [
                {
                    "judge_id": s.judge_id,
                    "winner_agent_id": s.winner_agent_id,
                    "winner_text_hash": s.winner_text_hash,
                    "reason": s.reason.value,
                    "signature": s.signature.hex(),
                }
                for s in self.judge_signatures
            ],
            "dissenting_judges": list(self.dissenting_judges),
            "constitutional_hash": self.constitutional_hash,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
            "candidates_digest": self.candidates_digest,
        }


def _candidates_digest(candidates: Sequence[FJACandidate]) -> str:
    """Sha256 over the ordered candidate set.

    Ordered by ``agent_id`` so the digest is independent of submission order.
    Bound into every judge signature to prevent cross-adjudication replay of
    a previously-captured honest signature into a fresh candidate set.
    """
    entries = sorted(
        (
            {
                "agent_id": c.agent_id,
                "text_hash": hashlib.sha256(c.text.encode("utf-8")).hexdigest(),
            }
            for c in candidates
        ),
        key=lambda e: e["agent_id"],
    )
    return hashlib.sha256(_canonical_json({"candidates": entries})).hexdigest()


def _signing_payload(
    context: _VoteContext,
) -> bytes:
    """Canonical byte payload a judge signs, with domain separation.

    The payload binds the judge-local decision to:
      * a per-adjudication ``session_id`` (nonce)
      * the exact candidate set via ``candidates_digest``
      * the ``constitutional_hash`` in force at adjudication time
      * the domain tag so signatures cannot be confused with any other
        Ed25519-signed JSON in the system.
    Any byte change anywhere in this payload invalidates the signature.
    """
    return _FFJA_VOTE_DOMAIN_TAG + _canonical_json(
        {
            "candidates_digest": context.candidates_digest,
            "constitutional_hash": context.constitutional_hash,
            "judge_id": context.judge_id,
            "reason": context.reason.value,
            "session_id": context.session_id,
            "winner_agent_id": context.winner_agent_id,
            "winner_text_hash": context.winner_text_hash,
        }
    )


def _text_hash(text: str | None) -> str:
    """Full 256-bit sha256 hex of a winner text, or sentinel for None."""
    if text is None:
        return _NO_WINNER_TEXT_HASH
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =============================================================================
# FederatedJudgeAnchor
# =============================================================================


class FederatedJudgeAnchor:
    """t-of-N threshold FJA. Byzantine-fault-tolerant for up to f = N - t failures."""

    def __init__(
        self,
        judges: Sequence[JudgeMember],
        threshold: int,
        *,
        per_judge_similarity_threshold: float = 0.85,
        max_workers: int | None = None,
    ) -> None:
        if len(judges) < 1:
            raise ValueError("federated judge anchor requires at least one judge")
        if threshold < 1 or threshold > len(judges):
            raise ValueError(f"threshold must satisfy 1 <= t <= N (t={threshold}, N={len(judges)})")
        seen_ids: set[str] = set()
        for j in judges:
            if j.judge_id in seen_ids:
                raise ValueError(f"duplicate judge_id: {j.judge_id}")
            seen_ids.add(j.judge_id)
            if not j.anchor.model_hash:
                raise ValueError(f"judge {j.judge_id} has empty model_hash")

        self._judges: list[JudgeMember] = list(judges)
        self._threshold = threshold
        self._per_judge_similarity_threshold = per_judge_similarity_threshold
        self._max_workers = max_workers if max_workers is not None else len(judges)
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._finalizer = weakref.finalize(self, self._executor.shutdown, wait=False)

    def close(self) -> None:
        """Shut down the cached judge executor."""
        self._finalizer.detach()
        self._executor.shutdown(wait=True)

    def __enter__(self) -> "FederatedJudgeAnchor":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    @property
    def num_judges(self) -> int:
        """N."""
        return len(self._judges)

    @property
    def threshold(self) -> int:
        """t."""
        return self._threshold

    # -- Core adjudication -------------------------------------------------

    def adjudicate(
        self,
        candidates: Sequence[FJACandidate],
        judge_private_keys: Mapping[str, bytes],
        *,
        session_id: str | None = None,
    ) -> FederatedQuorumResult:
        """Run all judges in parallel, collect signed votes, return federated result.

        ``session_id`` is an adjudication-specific nonce bound into every judge
        signature.  A fresh random id is generated when omitted; callers can
        pass a fixed value to reproduce a specific adjudication (e.g. tests,
        forensic replay).  Two adjudications over identical candidates but
        different session_ids produce different signatures — by design.
        """
        # Fail-fast: every registered judge must have a private key available.
        missing = [j.judge_id for j in self._judges if j.judge_id not in judge_private_keys]
        if missing:
            raise KeyError(f"missing private keys for judges: {missing}")

        session = session_id if session_id is not None else secrets.token_hex(16)
        cand_digest = _candidates_digest(candidates)

        signatures: list[JudgeSignature] = []
        dissenting: list[str] = []

        futures = {
            self._executor.submit(
                self._run_local_judge,
                _VoteContext(
                    judge_id=judge.judge_id,
                    session_id=session,
                    candidates_digest=cand_digest,
                    constitutional_hash=CONSTITUTIONAL_HASH,
                    anchor=judge.anchor,
                    candidates=candidates,
                    private_key_bytes=judge_private_keys[judge.judge_id],
                ),
            ): judge.judge_id
            for judge in self._judges
        }
        for future in as_completed(futures):
            judge_id = futures[future]
            try:
                sig = future.result()
            except Exception as exc:  # noqa: BLE001
                # Should not happen — _run_local_judge itself catches.
                # Fail-safe: isolate.
                _log_judge_exception("ffja.judge.unexpected_error", judge_id, exc)
                dissenting.append(judge_id)
                continue
            if sig.reason is FJADecisionReason.AGREED:
                signatures.append(sig)
            else:
                dissenting.append(judge_id)

        # Tally: only AGREED signatures count toward a winning coalition.
        # Group by (winner_agent_id, winner_text_hash).
        coalition: dict[tuple[str | None, str], list[JudgeSignature]] = {}
        for sig in signatures:
            key = (sig.winner_agent_id, sig.winner_text_hash)
            coalition.setdefault(key, []).append(sig)

        winning_sigs: list[JudgeSignature] = []
        winner_agent_id: str | None = None
        winner_text: str | None = None

        if coalition:
            # Deterministic tie-break: largest group, then lex on agent_id.
            best_key = max(
                coalition.keys(),
                key=lambda k: (len(coalition[k]), -1 if k[0] is None else 0, k[0] or ""),
            )
            if len(coalition[best_key]) >= self._threshold:
                winning_sigs = coalition[best_key]
                winner_agent_id = best_key[0]
                # Recover the winner text from any candidate matching the winner_agent_id.
                for c in candidates:
                    if c.agent_id == winner_agent_id:
                        winner_text = c.text
                        break

        agreed = len(winning_sigs) >= self._threshold

        # Non-winning AGREED judges are also dissenting (they agreed locally
        # but voted for a different candidate than the coalition).
        if agreed:
            winning_ids = {s.judge_id for s in winning_sigs}
            for sig in signatures:
                if sig.judge_id not in winning_ids:
                    dissenting.append(sig.judge_id)
        else:
            # Threshold not met — no coalition won. Every signer is a dissenter.
            dissenting.extend(s.judge_id for s in signatures)

        # Deduplicate dissenting while preserving first-seen order.
        deduped_dissent = list(dict.fromkeys(dissenting))

        logger.info(
            "ffja.adjudication.complete",
            agreed=agreed,
            threshold=self._threshold,
            num_judges=len(self._judges),
            winning=len(winning_sigs),
            dissenting=len(deduped_dissent),
        )

        return FederatedQuorumResult(
            agreed=agreed,
            threshold=self._threshold,
            num_judges=len(self._judges),
            winner_agent_id=winner_agent_id,
            winner_text=winner_text,
            judge_signatures=winning_sigs if agreed else [],
            dissenting_judges=deduped_dissent,
            constitutional_hash=CONSTITUTIONAL_HASH,
            created_at=datetime.now(UTC),
            session_id=session,
            candidates_digest=cand_digest,
        )

    # -- Per-judge local decision + sign -----------------------------------

    def _run_local_judge(
        self,
        context: _VoteContext,
    ) -> JudgeSignature:
        """Run one judge's local FJA, sign the outcome. Never raises."""
        try:
            if context.anchor is None:
                raise ValueError("missing judge anchor")
            quorum = FrozenJudgeQuorum(
                anchor=context.anchor,
                threshold=self._per_judge_similarity_threshold,
                min_quorum=2,
            )
            local: FJAQuorumResult = quorum.decide(context.candidates)
            reason = local.reason
            winner_agent_id = local.winner_agent_id if local.agreed else None
            winner_text_hash = _text_hash(local.winner_text if local.agreed else None)
        except Exception as exc:  # noqa: BLE001
            _log_judge_exception("ffja.local_judge.error", context.judge_id, exc)
            reason = FJADecisionReason.EMBEDDER_ERROR
            winner_agent_id = None
            winner_text_hash = _NO_WINNER_TEXT_HASH

        try:
            signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(context.private_key_bytes)
            payload = _signing_payload(
                replace(
                    context,
                    winner_agent_id=winner_agent_id,
                    winner_text_hash=winner_text_hash,
                    reason=reason,
                )
            )
            signature_bytes = signing_key.sign(payload)
        except Exception as exc:  # noqa: BLE001
            # Never leak exception messages in credential/signature paths.
            _log_judge_exception("ffja.sign.error", context.judge_id, exc)
            # Fail-closed: emit an EMBEDDER_ERROR signature with empty sig bytes.
            return JudgeSignature(
                judge_id=context.judge_id,
                winner_agent_id=None,
                winner_text_hash=_NO_WINNER_TEXT_HASH,
                reason=FJADecisionReason.EMBEDDER_ERROR,
                signature=b"",
            )

        return JudgeSignature(
            judge_id=context.judge_id,
            winner_agent_id=winner_agent_id,
            winner_text_hash=winner_text_hash,
            reason=reason,
            signature=signature_bytes,
        )


# =============================================================================
# Module-level verification entry point
# =============================================================================


def verify_federated_result(
    result: FederatedQuorumResult,
    judges: Sequence[JudgeMember],
) -> bool:
    """Re-verify every signature in a FederatedQuorumResult.

    External-auditor entry point.  Checks (in order):

    1. When ``result.agreed`` is True, the coalition size must satisfy the
       claimed threshold.  An attacker who strips signatures to trick a
       downstream consumer is caught here.
    2. When ``result.agreed`` is True, ``result.winner_text`` must hash to
       the same value every winning signature attests to.  An orchestrator
       that lies about the published text (while leaving hashes consistent
       with each other) is caught here.
    3. Every listed judge must be in the ``judges`` registry.
    4. Every signature must verify against the judge's public key over the
       full bound payload (domain tag, session_id, candidates_digest,
       constitutional_hash, judge_id, reason, winner_agent_id, text_hash).

    Non-agreed results with zero signatures pass trivially — there is
    nothing to verify and the auditor should inspect ``dissenting_judges``.
    """
    seen_judges: set[str] = set()
    for sig in result.judge_signatures:
        if sig.judge_id in seen_judges:
            logger.warning(
                "ffja.verify.duplicate_signer",
                judge_id=sig.judge_id,
            )
            return False
        seen_judges.add(sig.judge_id)

    if result.agreed and len(seen_judges) < result.threshold:
        logger.warning(
            "ffja.verify.coalition_too_small",
            got=len(seen_judges),
            threshold=result.threshold,
        )
        return False

    if result.agreed and result.winner_text is not None:
        expected_text_hash = _text_hash(result.winner_text)
        for sig in result.judge_signatures:
            if sig.winner_text_hash != expected_text_hash:
                logger.warning(
                    "ffja.verify.winner_text_hash_mismatch",
                    judge_id=sig.judge_id,
                )
                return False

    public_keys: dict[str, bytes] = {j.judge_id: j.public_key for j in judges}

    for sig in result.judge_signatures:
        pk_bytes = public_keys.get(sig.judge_id)
        if pk_bytes is None:
            logger.warning(
                "ffja.verify.unknown_judge",
                judge_id=sig.judge_id,
            )
            return False
        try:
            pk = ed25519.Ed25519PublicKey.from_public_bytes(pk_bytes)
            payload = _signing_payload(
                _VoteContext(
                    judge_id=sig.judge_id,
                    session_id=result.session_id,
                    candidates_digest=result.candidates_digest,
                    constitutional_hash=result.constitutional_hash,
                    winner_agent_id=sig.winner_agent_id,
                    winner_text_hash=sig.winner_text_hash,
                    reason=sig.reason,
                )
            )
            pk.verify(sig.signature, payload)
        except InvalidSignature:
            logger.warning(
                "ffja.verify.invalid_signature",
                judge_id=sig.judge_id,
            )
            return False
        except Exception as exc:  # noqa: BLE001
            _log_judge_exception("ffja.verify.error", sig.judge_id, exc)
            return False

    return True


__all__ = [
    "FederatedJudgeAnchor",
    "FederatedQuorumResult",
    "JudgeMember",
    "JudgeSignature",
    "verify_federated_result",
]
