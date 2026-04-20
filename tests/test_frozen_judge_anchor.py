"""
ACGS-2 Enhanced Agent Bus - Frozen Judge Anchor Tests
Constitutional Hash: 608508a9bd224290

Unit tests for the FJA quorum decision engine and supporting types.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

from enhanced_agent_bus.deliberation_layer.frozen_judge_anchor import (
    FJACandidate,
    FJADecisionReason,
    FJAQuorumResult,
    FrozenJudgeAnchorProtocol,
    FrozenJudgeQuorum,
    InMemoryFrozenJudgeAnchor,
    OnnxFrozenJudgeAnchor,
)
from enhanced_agent_bus.maci_imports import CONSTITUTIONAL_HASH

# Governance and constitutional compliance test markers
pytestmark = [pytest.mark.governance, pytest.mark.constitutional]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def anchor() -> InMemoryFrozenJudgeAnchor:
    """Default InMemory anchor for tests."""
    return InMemoryFrozenJudgeAnchor()


@pytest.fixture
def quorum(anchor: InMemoryFrozenJudgeAnchor) -> FrozenJudgeQuorum:
    """Default FrozenJudgeQuorum with InMemory anchor."""
    return FrozenJudgeQuorum(anchor=anchor, threshold=0.85, min_quorum=2)


# =============================================================================
# Test: Insufficient candidates
# =============================================================================


class TestInsufficientCandidates:
    """k < min_quorum must produce INSUFFICIENT_CANDIDATES."""

    def test_zero_candidates(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([])
        assert not result.agreed
        assert result.reason is FJADecisionReason.INSUFFICIENT_CANDIDATES
        assert result.winner_agent_id is None
        assert result.winner_text is None
        assert result.similarity_matrix == []
        assert result.quorum_size == 0

    def test_one_candidate(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("agent-a", "hello world")])
        assert not result.agreed
        assert result.reason is FJADecisionReason.INSUFFICIENT_CANDIDATES
        assert result.quorum_size == 1


# =============================================================================
# Test: Agreement — identical text
# =============================================================================


class TestAgreementIdenticalText:
    """Identical text → identical normalized vectors → cosine = 1.0 → AGREED."""

    def test_two_identical(self, quorum: FrozenJudgeQuorum) -> None:
        candidates = [
            FJACandidate("agent-a", "the constitutional anchor is frozen"),
            FJACandidate("agent-b", "the constitutional anchor is frozen"),
        ]
        result = quorum.decide(candidates)
        assert result.agreed
        assert result.reason is FJADecisionReason.AGREED
        assert result.mean_pairwise_similarity > 0.99

    def test_three_identical(self, quorum: FrozenJudgeQuorum) -> None:
        text = "identical governance output for quorum test"
        candidates = [FJACandidate(f"agent-{i}", text) for i in range(3)]
        result = quorum.decide(candidates)
        assert result.agreed
        assert result.reason is FJADecisionReason.AGREED
        assert result.winner_agent_id is not None

    def test_winner_is_set_when_agreed(self, quorum: FrozenJudgeQuorum) -> None:
        text = "agreed output"
        candidates = [
            FJACandidate("agent-a", text),
            FJACandidate("agent-b", text),
        ]
        result = quorum.decide(candidates)
        assert result.agreed
        assert result.winner_agent_id in {"agent-a", "agent-b"}
        assert result.winner_text == text


# =============================================================================
# Test: Disagreement — diverse text
# =============================================================================


class TestDisagreementDiverseText:
    """Very different texts → InMemory deterministic hash → low cosine → BELOW_THRESHOLD."""

    def test_diverse_two_candidates(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        quorum = FrozenJudgeQuorum(anchor=anchor, threshold=0.85, min_quorum=2)
        # Completely different strings produce uncorrelated SHA-256 digests
        candidates = [
            FJACandidate("agent-a", "alpha beta gamma delta epsilon"),
            FJACandidate("agent-b", "zymurgy quixotic fjord noctilucent"),
        ]
        result = quorum.decide(candidates)
        # With SHA-256-derived vectors the similarity will very likely be below 0.85
        # (the InMemory embedder is specifically adversarial for this)
        assert not result.agreed
        assert result.reason is FJADecisionReason.BELOW_THRESHOLD
        assert result.winner_agent_id is None
        assert result.winner_text is None

    def test_diverse_three_candidates(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        quorum = FrozenJudgeQuorum(anchor=anchor, threshold=0.85, min_quorum=2)
        candidates = [
            FJACandidate("a", "xylophone"),
            FJACandidate("b", "quantum entanglement manifold"),
            FJACandidate("c", "red octopus swimming 99"),
        ]
        result = quorum.decide(candidates)
        assert not result.agreed or result.mean_pairwise_similarity >= 0.85


# =============================================================================
# Test: Winner selection — tie-break by agent_id lexicographic
# =============================================================================


class TestWinnerSelectionTieBreak:
    """When scores are tied, lexicographically smallest agent_id wins."""

    def test_tie_break_lexicographic(self, quorum: FrozenJudgeQuorum) -> None:
        # All identical text → all scores identical → tie-break by agent_id
        text = "tie break test output"
        candidates = [
            FJACandidate("zebra", text),
            FJACandidate("alpha", text),
            FJACandidate("mango", text),
        ]
        result = quorum.decide(candidates)
        assert result.agreed
        assert result.winner_agent_id == "alpha"

    def test_tie_break_two_agents(self, quorum: FrozenJudgeQuorum) -> None:
        text = "same output"
        candidates = [
            FJACandidate("z-agent", text),
            FJACandidate("a-agent", text),
        ]
        result = quorum.decide(candidates)
        assert result.agreed
        assert result.winner_agent_id == "a-agent"


# =============================================================================
# Test: Hash mismatch raises ValueError on FrozenJudgeQuorum construction
# =============================================================================


class TestHashMismatch:
    """expected_model_hash != anchor.model_hash must raise ValueError."""

    def test_hash_mismatch_raises(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        with pytest.raises(ValueError, match="judge model hash mismatch"):
            FrozenJudgeQuorum(
                anchor=anchor,
                expected_model_hash="sha256:definitely-wrong-hash",
            )

    def test_correct_hash_does_not_raise(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        # Should not raise
        quorum = FrozenJudgeQuorum(
            anchor=anchor,
            expected_model_hash=anchor.model_hash,
        )
        assert quorum is not None

    def test_none_hash_skips_check(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        quorum = FrozenJudgeQuorum(anchor=anchor, expected_model_hash=None)
        assert quorum is not None


# =============================================================================
# Test: Constitutional hash in audit dict
# =============================================================================


class TestConstitutionalHashInAudit:
    """to_audit_dict() must carry constitutional_hash and judge_model_hash."""

    def test_constitutional_hash_present(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        audit = result.to_audit_dict()
        assert audit["constitutional_hash"] == CONSTITUTIONAL_HASH
        assert audit["constitutional_hash"] == "608508a9bd224290"

    def test_judge_model_hash_present(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        audit = result.to_audit_dict()
        assert "judge_model_hash" in audit
        assert audit["judge_model_hash"].startswith("sha256:inmemory-fake-")

    def test_custom_constitutional_hash(self, anchor: InMemoryFrozenJudgeAnchor) -> None:
        custom_hash = "deadbeef00000000"
        quorum = FrozenJudgeQuorum(anchor=anchor, constitutional_hash=custom_hash)
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        assert result.to_audit_dict()["constitutional_hash"] == custom_hash


# =============================================================================
# Test: Audit record shape (all fields present, json.dumps-safe)
# =============================================================================


class TestAuditRecordShape:
    """to_audit_dict() must be json.dumps-able and contain all required fields."""

    REQUIRED_FIELDS = {
        "agreed",
        "reason",
        "winner_agent_id",
        "winner_text",
        "similarity_matrix",
        "mean_pairwise_similarity",
        "quorum_size",
        "threshold",
        "judge_model_hash",
        "constitutional_hash",
        "created_at",
    }

    def test_all_fields_present(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "hello"), FJACandidate("b", "hello")])
        audit = result.to_audit_dict()
        assert self.REQUIRED_FIELDS == set(audit.keys())

    def test_json_serializable(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "hello"), FJACandidate("b", "hello")])
        audit = result.to_audit_dict()
        dumped = json.dumps(audit)
        loaded = json.loads(dumped)
        assert loaded["constitutional_hash"] == CONSTITUTIONAL_HASH

    def test_similarity_matrix_is_list_of_lists(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "foo"), FJACandidate("b", "bar")])
        audit = result.to_audit_dict()
        mat = audit["similarity_matrix"]
        assert isinstance(mat, list)
        assert all(isinstance(row, list) for row in mat)
        assert all(isinstance(v, float) for row in mat for v in row)

    def test_created_at_is_iso8601(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "t"), FJACandidate("b", "t")])
        audit = result.to_audit_dict()
        # Must be parseable as datetime
        from datetime import datetime

        dt = datetime.fromisoformat(audit["created_at"])
        assert dt.tzinfo is not None  # UTC-aware

    def test_insufficient_audit_shape(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([])
        audit = result.to_audit_dict()
        assert self.REQUIRED_FIELDS == set(audit.keys())
        assert json.dumps(audit)

    def test_reason_is_string(self, quorum: FrozenJudgeQuorum) -> None:
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        audit = result.to_audit_dict()
        assert isinstance(audit["reason"], str)


# =============================================================================
# Test: Embedder error — fail closed, EMBEDDER_ERROR reason
# =============================================================================


class TestEmbedderError:
    """When anchor.embed() raises, FJA returns EMBEDDER_ERROR and does not re-raise."""

    def test_embedder_error_fail_closed(self) -> None:
        class BrokenAnchor:
            model_hash = "sha256:broken"

            def embed(self, text: str) -> None:
                raise RuntimeError("model unavailable")

        quorum = FrozenJudgeQuorum(anchor=BrokenAnchor())  # type: ignore[arg-type]
        candidates = [FJACandidate("a", "hello"), FJACandidate("b", "world")]
        result = quorum.decide(candidates)
        assert not result.agreed
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_error_no_exception_raised(self) -> None:
        class FlakeyAnchor:
            model_hash = "sha256:flakey"

            def embed(self, text: str) -> None:
                raise ValueError("embedding failure")

        quorum = FrozenJudgeQuorum(anchor=FlakeyAnchor())  # type: ignore[arg-type]
        # Must not raise
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "y")])
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_malformed_output_wrong_ndim(self) -> None:
        # Regression: a pluggable embedder that returns a 2-D array instead
        # of a flat vector must resolve to EMBEDDER_ERROR, not an uncaught
        # crash in the normalization / matmul path.
        import numpy as np

        class BadShapeAnchor:
            model_hash = "sha256:badshape"

            def embed(self, text: str):  # noqa: ANN001, ARG002
                return np.zeros((3, 4), dtype=np.float32)

        quorum = FrozenJudgeQuorum(anchor=BadShapeAnchor())  # type: ignore[arg-type]
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "y")])
        assert not result.agreed
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_malformed_output_mixed_hidden_size(self) -> None:
        import numpy as np

        class MixedSizeAnchor:
            model_hash = "sha256:mixed"
            _counter = 0

            def embed(self, text: str):  # noqa: ANN001, ARG002
                self._counter += 1
                return np.ones(3 + self._counter, dtype=np.float32)

        quorum = FrozenJudgeQuorum(anchor=MixedSizeAnchor())  # type: ignore[arg-type]
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "y")])
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_malformed_output_nan_value(self) -> None:
        import numpy as np

        class NanAnchor:
            model_hash = "sha256:nan"

            def embed(self, text: str):  # noqa: ANN001, ARG002
                return np.array([1.0, float("nan"), 2.0], dtype=np.float32)

        quorum = FrozenJudgeQuorum(anchor=NanAnchor())  # type: ignore[arg-type]
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "y")])
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_malformed_output_non_unit_norm(self) -> None:
        class _NonNormalizingAnchor(InMemoryFrozenJudgeAnchor):
            def embed(self, text: str):  # noqa: ANN001
                return super().embed(text) * 2.0

        quorum = FrozenJudgeQuorum(anchor=_NonNormalizingAnchor())
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        assert not result.agreed
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR

    def test_embedder_malformed_output_non_array_return(self) -> None:
        # Non-numeric return (e.g. embedder stub returns a string) must be
        # converted + caught at the np.asarray() boundary, not propagated.
        class StringAnchor:
            model_hash = "sha256:str"

            def embed(self, text: str):  # noqa: ANN001, ARG002
                return "not a vector"

        quorum = FrozenJudgeQuorum(anchor=StringAnchor())  # type: ignore[arg-type]
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "y")])
        assert result.reason is FJADecisionReason.EMBEDDER_ERROR


# =============================================================================
# Test: ONNX lazy import guard
# =============================================================================


class TestOnnxLazyImportGuard:
    """Core module must import without onnxruntime. OnnxFrozenJudgeAnchor errors when absent."""

    def test_core_module_imports_without_onnx(self) -> None:
        """The module itself must be importable regardless of onnxruntime presence."""
        import enhanced_agent_bus.deliberation_layer.frozen_judge_anchor as fja_mod

        assert hasattr(fja_mod, "FrozenJudgeQuorum")
        assert hasattr(fja_mod, "InMemoryFrozenJudgeAnchor")
        assert hasattr(fja_mod, "OnnxFrozenJudgeAnchor")

    def test_inmemory_works_without_onnx(self) -> None:
        """InMemoryFrozenJudgeAnchor must function regardless of onnxruntime."""
        anchor = InMemoryFrozenJudgeAnchor()
        quorum = FrozenJudgeQuorum(anchor=anchor)
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        assert result.quorum_size == 2

    def test_onnx_raises_when_absent(self, tmp_path: Path) -> None:
        """If onnxruntime is NOT installed, OnnxFrozenJudgeAnchor must raise RuntimeError."""
        if importlib.util.find_spec("onnxruntime") is not None:
            pytest.skip("onnxruntime is installed; cannot test absent-dep guard")
        with pytest.raises(RuntimeError, match="enhanced_agent_bus\\[ml\\] extra"):
            OnnxFrozenJudgeAnchor(
                model_path=tmp_path,  # type: ignore[arg-type]
                tokenizer_path=tmp_path,  # type: ignore[arg-type]
                expected_hash="sha256:irrelevant",
            )


# =============================================================================
# Test: InMemory embed determinism and normalization
# =============================================================================


class TestInMemoryAnchor:
    """Verify determinism and L2-normalization of InMemoryFrozenJudgeAnchor."""

    def test_deterministic(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        v1 = anchor.embed("hello world")
        v2 = anchor.embed("hello world")
        import numpy as np

        assert np.allclose(v1, v2)

    def test_l2_normalized(self) -> None:
        import numpy as np

        anchor = InMemoryFrozenJudgeAnchor()
        v = anchor.embed("test normalization")
        norm = float(np.linalg.norm(v))
        assert abs(norm - 1.0) < 1e-6

    def test_different_texts_different_vectors(self) -> None:
        import numpy as np

        anchor = InMemoryFrozenJudgeAnchor()
        v1 = anchor.embed("apple")
        v2 = anchor.embed("banana")
        assert not np.allclose(v1, v2)

    def test_custom_dim(self) -> None:
        import numpy as np

        anchor = InMemoryFrozenJudgeAnchor(dim=32)
        v = anchor.embed("dimensionality test")
        assert v.shape == (32,)
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-6

    def test_default_model_hash(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        assert anchor.model_hash == "sha256:inmemory-fake-16"

    def test_custom_model_hash(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor(model_hash="sha256:custom-test-hash")
        assert anchor.model_hash == "sha256:custom-test-hash"


# =============================================================================
# Test: Protocol conformance
# =============================================================================


class TestProtocolConformance:
    """InMemoryFrozenJudgeAnchor must satisfy FrozenJudgeAnchorProtocol."""

    def test_inmemory_satisfies_protocol(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        assert isinstance(anchor, FrozenJudgeAnchorProtocol)

    def test_quorum_result_fields(self) -> None:
        anchor = InMemoryFrozenJudgeAnchor()
        quorum = FrozenJudgeQuorum(anchor=anchor)
        result = quorum.decide([FJACandidate("a", "x"), FJACandidate("b", "x")])
        assert isinstance(result, FJAQuorumResult)
        assert isinstance(result.reason, FJADecisionReason)
        assert isinstance(result.agreed, bool)
        assert isinstance(result.similarity_matrix, list)
