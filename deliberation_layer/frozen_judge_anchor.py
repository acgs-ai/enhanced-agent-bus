"""Frozen Judge Anchor (FJA). Breaks the recursive-LLM-judge regress via pinned-hash embedding quorum. Constitutional Hash: 608508a9bd224290"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np
import structlog

from enhanced_agent_bus.maci_imports import CONSTITUTIONAL_HASH

logger = structlog.get_logger(__name__)


# =============================================================================
# Protocol
# =============================================================================


@runtime_checkable
class FrozenJudgeAnchorProtocol(Protocol):
    """Embedder boundary — the frozen judge that must not be an LLM."""

    model_hash: str

    def embed(self, text: str) -> np.ndarray:
        """Return an L2-normalized float64 vector for text."""
        ...


# =============================================================================
# Value types
# =============================================================================


@dataclass(frozen=True)
class FJACandidate:
    """A single agent response candidate for quorum evaluation."""

    agent_id: str
    text: str


class FJADecisionReason(Enum):
    """Outcome reason for a FJA quorum decision."""

    AGREED = "agreed"
    BELOW_THRESHOLD = "below_threshold"
    INSUFFICIENT_CANDIDATES = "insufficient_candidates"
    HASH_MISMATCH = "hash_mismatch"
    EMBEDDER_ERROR = "embedder_error"


@dataclass(frozen=True)
class FJAQuorumResult:
    """Full audit record for a single FJA quorum decision."""

    agreed: bool
    reason: FJADecisionReason
    winner_agent_id: str | None
    winner_text: str | None
    similarity_matrix: list[list[float]]
    mean_pairwise_similarity: float
    quorum_size: int
    threshold: float
    judge_model_hash: str
    constitutional_hash: str
    created_at: datetime

    def to_audit_dict(self) -> dict[str, Any]:
        """Flat audit dict matching the MACIValidationResult pattern. json.dumps-safe."""
        return {
            "agreed": self.agreed,
            "reason": self.reason.value,
            "winner_agent_id": self.winner_agent_id,
            "winner_text": self.winner_text,
            "similarity_matrix": self.similarity_matrix,
            "mean_pairwise_similarity": self.mean_pairwise_similarity,
            "quorum_size": self.quorum_size,
            "threshold": self.threshold,
            "judge_model_hash": self.judge_model_hash,
            "constitutional_hash": self.constitutional_hash,
            "created_at": self.created_at.isoformat(),
        }


# =============================================================================
# InMemory (test) implementation
# =============================================================================


class InMemoryFrozenJudgeAnchor:
    """Deterministic fake embedder. Tests only."""

    def __init__(
        self,
        model_hash: str | None = None,
        dim: int = 16,
    ) -> None:
        self._dim = dim
        self.model_hash: str = model_hash or f"sha256:inmemory-fake-{dim}"

    def embed(self, text: str) -> np.ndarray:
        """SHA-256(text) → first dim*4 bytes → dim uint32s → normalized float64."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        needed = self._dim * 4
        repeated = (digest * ((needed // len(digest)) + 1))[:needed]
        raw = np.frombuffer(repeated, dtype=">u4").astype(np.float64)
        norm = np.linalg.norm(raw)
        if norm == 0.0:
            # Degenerate zero vector — return unit along first axis
            result = np.zeros(self._dim, dtype=np.float64)
            result[0] = 1.0
            return result
        return raw / norm


# =============================================================================
# ONNX (production) implementation
# =============================================================================


class OnnxFrozenJudgeAnchor:
    """Production backend: MiniLM-L6-v2-compatible mean-pool + L2-norm embedder."""

    def __init__(
        self,
        model_path: Path,
        tokenizer_path: Path,
        expected_hash: str,
    ) -> None:
        try:
            import onnxruntime as ort  # type: ignore[import-untyped]
            import tokenizers as _tok  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "OnnxFrozenJudgeAnchor requires enhanced_agent_bus[ml] extra (onnxruntime, tokenizers)"
            ) from None

        computed = "sha256:" + hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
        if not hmac.compare_digest(computed, expected_hash):
            # Do not leak the computed hash — it would confirm tampering to an attacker.
            logger.warning(
                "fja.onnx.hash_mismatch",
                expected=expected_hash,
                computed=computed,
            )
            raise ValueError("judge model hash mismatch")
        self.model_hash: str = computed

        self._session = ort.InferenceSession(str(model_path))
        self._tokenizer = _tok.Tokenizer.from_file(str(tokenizer_path))
        self._tokenizer.enable_truncation(max_length=512)
        self._tokenizer.enable_padding()

    def embed(self, text: str) -> np.ndarray:
        """Tokenize → run ONNX → mean-pool → L2-normalize."""
        encoding = self._tokenizer.encode(text)
        input_ids = np.array([encoding.ids], dtype=np.int64)
        attention_mask = np.array([encoding.attention_mask], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        outputs = self._session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )
        # outputs[0]: (1, seq_len, hidden) — mean-pool over non-padding tokens
        hidden: np.ndarray = outputs[0][0]  # (seq_len, hidden)
        mask = attention_mask[0].astype(np.float64)  # (seq_len,)
        pooled = (hidden * mask[:, None]).sum(axis=0) / (mask.sum() + 1e-9)
        norm = np.linalg.norm(pooled)
        if norm == 0.0:
            return pooled
        return (pooled / norm).astype(np.float64)


# =============================================================================
# FrozenJudgeQuorum — the decision engine
# =============================================================================


class FrozenJudgeQuorum:
    """Semantic quorum using a frozen, hash-verified embedder. Fail-closed."""

    def __init__(
        self,
        anchor: FrozenJudgeAnchorProtocol,
        threshold: float = 0.85,
        min_quorum: int = 2,
        expected_model_hash: str | None = None,
        constitutional_hash: str = CONSTITUTIONAL_HASH,
    ) -> None:
        if expected_model_hash is not None and not hmac.compare_digest(
            expected_model_hash, anchor.model_hash
        ):
            # Do not leak the anchor's actual hash in the error message.
            logger.warning(
                "fja.quorum.hash_mismatch",
                expected=expected_model_hash,
                actual=anchor.model_hash,
            )
            raise ValueError("judge model hash mismatch")
        if constitutional_hash != CONSTITUTIONAL_HASH:
            # Caller override is permitted but MUST be audited — this is the load-bearing
            # governance invariant for FJA results.
            logger.warning(
                "fja.constitutional_hash.override",
                expected=CONSTITUTIONAL_HASH,
                actual=constitutional_hash,
            )
        self._anchor = anchor
        self._threshold = threshold
        self._min_quorum = min_quorum
        self._constitutional_hash = constitutional_hash

    def decide(self, candidates: Sequence[FJACandidate]) -> FJAQuorumResult:
        """Run FJA quorum decision. Never raises — fail-closed via reason enum."""
        k = len(candidates)
        now = datetime.now(UTC)

        def _fail(reason: FJADecisionReason) -> FJAQuorumResult:
            return FJAQuorumResult(
                agreed=False,
                reason=reason,
                winner_agent_id=None,
                winner_text=None,
                similarity_matrix=[],
                mean_pairwise_similarity=0.0,
                quorum_size=k,
                threshold=self._threshold,
                judge_model_hash=self._anchor.model_hash,
                constitutional_hash=self._constitutional_hash,
                created_at=now,
            )

        # Step 1: guard insufficient candidates
        if k < self._min_quorum:
            logger.debug(
                "fja.insufficient_candidates",
                k=k,
                min_quorum=self._min_quorum,
            )
            return _fail(FJADecisionReason.INSUFFICIENT_CANDIDATES)

        # Step 2: embed all candidates.  The embedder is a pluggable protocol
        # boundary — malformed output (wrong dtype, non-vector shape, mixed
        # hidden sizes, NaN/Inf, non-normalized vectors) is a realistic failure
        # mode and must resolve to EMBEDDER_ERROR, not an uncaught ValueError
        # that takes down the caller.  Shape, dtype, and stack/matmul are all
        # protected here.
        vecs: list[np.ndarray] = []
        expected_hidden: int | None = None
        for cand in candidates:
            try:
                vec_raw = self._anchor.embed(cand.text)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "fja.embedder_error",
                    agent_id=cand.agent_id,
                    exc_type=type(exc).__name__,
                )
                return _fail(FJADecisionReason.EMBEDDER_ERROR)
            try:
                vec = np.asarray(vec_raw, dtype=np.float64)
                if vec.ndim != 1 or vec.size == 0:
                    raise ValueError(
                        f"embedding must be 1-D non-empty, got ndim={vec.ndim} size={vec.size}"
                    )
                if not np.isfinite(vec).all():
                    raise ValueError("embedding contains NaN or Inf")
                if expected_hidden is None:
                    expected_hidden = int(vec.shape[0])
                elif int(vec.shape[0]) != expected_hidden:
                    raise ValueError(
                        f"embedding hidden size {vec.shape[0]} != expected {expected_hidden}"
                    )
                norm = float(np.linalg.norm(vec))
                if abs(norm - 1.0) >= 1e-5:
                    raise ValueError(f"embedding not L2-normalized, norm={norm:.6f}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "fja.embedder_malformed_output",
                    agent_id=cand.agent_id,
                    exc_type=type(exc).__name__,
                )
                return _fail(FJADecisionReason.EMBEDDER_ERROR)
            vecs.append(vec)

        # Step 3: k×k cosine similarity matrix (vectors already normalized → dot product)
        try:
            mat = np.stack(vecs)  # (k, hidden)
            sim_matrix: np.ndarray = mat @ mat.T  # (k, k)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "fja.similarity_matrix_error",
                exc_type=type(exc).__name__,
            )
            return _fail(FJADecisionReason.EMBEDDER_ERROR)

        sim_list: list[list[float]] = sim_matrix.tolist()

        # Step 4: per-candidate score = mean of sim(i, j) for j != i
        if k == 1:
            scores = np.zeros(1, dtype=np.float64)
        else:
            scores = (sim_matrix.sum(axis=1) - np.diag(sim_matrix)) / (k - 1)

        # Step 5: mean pairwise similarity (off-diagonal, no self-sim)
        if k == 1:
            mean_pairwise = 0.0
        else:
            mean_pairwise = float((sim_matrix.sum() - np.trace(sim_matrix)) / (k * (k - 1)))

        agreed = mean_pairwise >= self._threshold

        logger.debug(
            "fja.decision",
            agreed=agreed,
            mean_pairwise=mean_pairwise,
            threshold=self._threshold,
            k=k,
        )

        # Step 6: winner selection (only if agreed)
        winner_agent_id: str | None = None
        winner_text: str | None = None
        if agreed:
            best_score = max(scores)
            best_candidates = [candidates[i] for i, s in enumerate(scores) if s == best_score]
            # Tie-break: lexicographic by agent_id
            winner = min(best_candidates, key=lambda c: c.agent_id)
            winner_agent_id = winner.agent_id
            winner_text = winner.text

        reason = FJADecisionReason.AGREED if agreed else FJADecisionReason.BELOW_THRESHOLD

        return FJAQuorumResult(
            agreed=agreed,
            reason=reason,
            winner_agent_id=winner_agent_id,
            winner_text=winner_text,
            similarity_matrix=sim_list,
            mean_pairwise_similarity=mean_pairwise,
            quorum_size=k,
            threshold=self._threshold,
            judge_model_hash=self._anchor.model_hash,
            constitutional_hash=self._constitutional_hash,
            created_at=now,
        )


__all__ = [
    "FJACandidate",
    "FJADecisionReason",
    "FJAQuorumResult",
    "FrozenJudgeAnchorProtocol",
    "FrozenJudgeQuorum",
    "InMemoryFrozenJudgeAnchor",
    "OnnxFrozenJudgeAnchor",
]
