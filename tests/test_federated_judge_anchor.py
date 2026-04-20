"""
ACGS-2 Enhanced Agent Bus - Federated Judge Anchor (fFJA) Tests
Constitutional Hash: 608508a9bd224290

Unit tests for threshold-signed t-of-N federated judge adjudication.
"""

from __future__ import annotations

import time
from collections.abc import Mapping

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from enhanced_agent_bus.deliberation_layer.federated_judge_anchor import (
    FederatedJudgeAnchor,
    FederatedQuorumResult,
    JudgeMember,
    JudgeSignature,
    verify_federated_result,
)
from enhanced_agent_bus.deliberation_layer.frozen_judge_anchor import (
    FJACandidate,
    FJADecisionReason,
    InMemoryFrozenJudgeAnchor,
)

pytestmark = [pytest.mark.governance, pytest.mark.constitutional]


# =============================================================================
# Fake embedder + keygen helpers
# =============================================================================


class FakeEmbedder(InMemoryFrozenJudgeAnchor):
    """InMemory judge anchor with the legacy test constructor shape."""

    def __init__(self, model_hash: str, bias: str = "") -> None:
        super().__init__(model_hash=model_hash or "sha256:test-placeholder")
        self.model_hash = model_hash
        self._bias = bias


class SlowFakeEmbedder(FakeEmbedder):
    """FakeEmbedder that sleeps to prove parallel execution."""

    def __init__(self, model_hash: str, sleep_s: float, bias: str = "") -> None:
        super().__init__(model_hash=model_hash, bias=bias)
        self._sleep_s = sleep_s

    def embed(self, text: str) -> np.ndarray:
        time.sleep(self._sleep_s)
        return super().embed(text)


class ExplodingEmbedder(InMemoryFrozenJudgeAnchor):
    """Embedder whose embed() always raises. Used to simulate a Byzantine/failing judge."""

    def __init__(self, model_hash: str) -> None:
        super().__init__(model_hash=model_hash)

    def embed(self, text: str):  # noqa: ANN001, ARG002
        raise RuntimeError("embedder simulated failure")


def _keypair() -> tuple[bytes, bytes]:
    """Generate (private_key_bytes, public_key_bytes) — raw 32 bytes each."""
    sk = ed25519.Ed25519PrivateKey.generate()
    sk_bytes = sk.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    pk_bytes = sk.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return sk_bytes, pk_bytes


def _build_judges(
    n: int,
    *,
    biases: list[str] | None = None,
    exploding_indices: set[int] | None = None,
    sleep_s: float | None = None,
) -> tuple[list[JudgeMember], dict[str, bytes]]:
    """Build N judges with fresh keys. Returns (members, priv_key_map)."""
    if biases is None:
        biases = [""] * n
    if exploding_indices is None:
        exploding_indices = set()

    members: list[JudgeMember] = []
    priv: dict[str, bytes] = {}
    for i in range(n):
        judge_id = f"judge-{i:02d}"
        model_hash = f"sha256:fake-judge-{i}"
        anchor: FakeEmbedder | ExplodingEmbedder
        if i in exploding_indices:
            anchor = ExplodingEmbedder(model_hash=model_hash)
        elif sleep_s is not None:
            anchor = SlowFakeEmbedder(model_hash=model_hash, sleep_s=sleep_s, bias=biases[i])
        else:
            anchor = FakeEmbedder(model_hash=model_hash, bias=biases[i])
        sk_bytes, pk_bytes = _keypair()
        members.append(JudgeMember(judge_id=judge_id, public_key=pk_bytes, anchor=anchor))
        priv[judge_id] = sk_bytes
    return members, priv


def _consensus_candidates() -> list[FJACandidate]:
    """A set of candidates designed to reach semantic consensus under shared embedding."""
    base = "The policy requires fail-closed validation with full audit trails."
    return [
        FJACandidate(agent_id="agent-a", text=base),
        FJACandidate(agent_id="agent-b", text=base),
        FJACandidate(agent_id="agent-c", text=base),
    ]


def _divergent_candidates() -> list[FJACandidate]:
    """Wildly different texts — unlikely to hit a per-judge similarity >= 0.85."""
    return [
        FJACandidate(agent_id="agent-a", text="alpha"),
        FJACandidate(agent_id="agent-b", text="beta delta gamma zeta kappa"),
        FJACandidate(agent_id="agent-c", text="QWERTY 123 !!!"),
    ]


# =============================================================================
# Constructor validation
# =============================================================================


class TestConstructorValidation:
    def test_constructor_rejects_zero_judges(self) -> None:
        with pytest.raises(ValueError):
            FederatedJudgeAnchor(judges=[], threshold=1)

    def test_constructor_rejects_threshold_out_of_range(self) -> None:
        judges, _ = _build_judges(3)
        with pytest.raises(ValueError):
            FederatedJudgeAnchor(judges=judges, threshold=0)
        with pytest.raises(ValueError):
            FederatedJudgeAnchor(judges=judges, threshold=4)

    def test_constructor_rejects_duplicate_judge_ids(self) -> None:
        _, pk1 = _keypair()
        _, pk2 = _keypair()
        anchor_a = FakeEmbedder(model_hash="sha256:a")
        anchor_b = FakeEmbedder(model_hash="sha256:b")
        judges = [
            JudgeMember(judge_id="dup", public_key=pk1, anchor=anchor_a),
            JudgeMember(judge_id="dup", public_key=pk2, anchor=anchor_b),
        ]
        with pytest.raises(ValueError):
            FederatedJudgeAnchor(judges=judges, threshold=1)

    def test_constructor_rejects_empty_model_hash(self) -> None:
        _, pk = _keypair()
        judges = [
            JudgeMember(
                judge_id="x",
                public_key=pk,
                anchor=FakeEmbedder(model_hash=""),
            )
        ]
        with pytest.raises(ValueError):
            FederatedJudgeAnchor(judges=judges, threshold=1)


# =============================================================================
# Core adjudication — agreement and disagreement
# =============================================================================


class TestThresholdAgreement:
    def test_t_of_n_agreement_on_consensus(self) -> None:
        # 4 judges all share the same (empty) bias → they all agree.
        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)

        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert result.agreed is True
        assert len(result.judge_signatures) >= 3
        assert result.winner_agent_id is not None
        assert result.winner_text is not None
        assert all(s.reason is FJADecisionReason.AGREED for s in result.judge_signatures)

    def test_threshold_not_met_is_not_agreed(self) -> None:
        # 4 judges with 4 different biases → each local FJA likely
        # below-threshold on the divergent candidates → no AGREED coalition.
        judges, priv = _build_judges(4, biases=["alpha", "beta", "gamma", "delta"])
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)

        result = ffja.adjudicate(_divergent_candidates(), priv)

        assert result.agreed is False
        assert result.judge_signatures == []
        assert result.winner_agent_id is None


# =============================================================================
# Byzantine resilience
# =============================================================================


class TestByzantineResilience:
    def test_single_byzantine_judge_cannot_flip_verdict(self) -> None:
        # 3 honest + 1 exploding → t=3 coalition of honest judges survives.
        judges, priv = _build_judges(4, exploding_indices={3})
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)

        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert result.agreed is True
        assert len(result.judge_signatures) == 3
        assert "judge-03" in result.dissenting_judges
        # Every signing judge is an AGREED judge.
        assert all(s.reason is FJADecisionReason.AGREED for s in result.judge_signatures)

    def test_exception_in_one_judge_is_isolated(self) -> None:
        judges, priv = _build_judges(3, exploding_indices={1})
        ffja = FederatedJudgeAnchor(judges=judges, threshold=2)

        # Must not raise.
        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert "judge-01" in result.dissenting_judges
        # Other two honest judges should still form a 2-of-3 coalition.
        assert result.agreed is True
        assert len(result.judge_signatures) == 2


# =============================================================================
# Missing private keys
# =============================================================================


class TestMissingKeys:
    def test_missing_private_key_raises_keyerror(self) -> None:
        judges, priv = _build_judges(3)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=2)
        del priv["judge-01"]
        with pytest.raises(KeyError):
            ffja.adjudicate(_consensus_candidates(), priv)


# =============================================================================
# Signature verification
# =============================================================================


class TestVerifyFederatedResult:
    def test_verify_federated_result_valid(self) -> None:
        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)
        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert result.agreed is True
        assert verify_federated_result(result, judges) is True

    def test_verify_federated_result_rejects_forged_signature(self) -> None:
        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)
        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert len(result.judge_signatures) >= 1
        # Flip one byte of one signature → must fail verification.
        target = result.judge_signatures[0]
        flipped = bytes([target.signature[0] ^ 0x01]) + target.signature[1:]
        forged = JudgeSignature(
            judge_id=target.judge_id,
            winner_agent_id=target.winner_agent_id,
            winner_text_hash=target.winner_text_hash,
            reason=target.reason,
            signature=flipped,
        )
        tampered_sigs = [forged, *result.judge_signatures[1:]]
        tampered = FederatedQuorumResult(
            agreed=result.agreed,
            threshold=result.threshold,
            num_judges=result.num_judges,
            winner_agent_id=result.winner_agent_id,
            winner_text=result.winner_text,
            judge_signatures=tampered_sigs,
            dissenting_judges=result.dissenting_judges,
            constitutional_hash=result.constitutional_hash,
            created_at=result.created_at,
        )

        assert verify_federated_result(tampered, judges) is False

    def test_verify_federated_result_rejects_wrong_public_key(self) -> None:
        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)
        result = ffja.adjudicate(_consensus_candidates(), priv)

        # Swap one judge's public key for a freshly-generated unrelated one.
        _, bogus_pk = _keypair()
        swapped = []
        swapped_one = False
        for j in judges:
            if not swapped_one and any(s.judge_id == j.judge_id for s in result.judge_signatures):
                swapped.append(
                    JudgeMember(judge_id=j.judge_id, public_key=bogus_pk, anchor=j.anchor)
                )
                swapped_one = True
            else:
                swapped.append(j)

        assert swapped_one
        assert verify_federated_result(result, swapped) is False

    def test_verify_federated_result_rejects_duplicate_signer(self) -> None:
        # Regression: a malicious orchestrator must not be able to satisfy
        # the threshold by replaying one valid signature N times.
        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)
        result = ffja.adjudicate(_consensus_candidates(), priv)

        assert result.agreed is True
        assert len(result.judge_signatures) >= 1
        replayed = result.judge_signatures[0]

        forged = FederatedQuorumResult(
            session_id=result.session_id,
            candidates_digest=result.candidates_digest,
            agreed=True,
            threshold=3,
            num_judges=result.num_judges,
            winner_agent_id=result.winner_agent_id,
            winner_text=result.winner_text,
            judge_signatures=[replayed, replayed, replayed],
            dissenting_judges=result.dissenting_judges,
            constitutional_hash=result.constitutional_hash,
            created_at=result.created_at,
        )

        assert verify_federated_result(forged, judges) is False


# =============================================================================
# Canonical JSON determinism
# =============================================================================


class TestCanonicalSigning:
    def test_canonical_signing_deterministic_for_fixed_session(self) -> None:
        # Ed25519 is deterministic over the canonical payload, and the
        # signing payload now binds session_id.  Two adjudications that
        # pin the SAME session_id (reproducible replay) produce identical
        # signatures.  Without a pinned session_id signatures would
        # (correctly) differ — that's the replay defence.
        judges, priv = _build_judges(1)
        ffja1 = FederatedJudgeAnchor(judges=judges, threshold=1)
        ffja2 = FederatedJudgeAnchor(judges=judges, threshold=1)

        candidates = _consensus_candidates()
        fixed_session = "test-session-fixed-nonce"
        r1 = ffja1.adjudicate(candidates, priv, session_id=fixed_session)
        r2 = ffja2.adjudicate(candidates, priv, session_id=fixed_session)

        assert len(r1.judge_signatures) == 1
        assert len(r2.judge_signatures) == 1
        s1 = r1.judge_signatures[0]
        s2 = r2.judge_signatures[0]
        assert s1.signature == s2.signature
        assert s1.winner_agent_id == s2.winner_agent_id
        assert s1.winner_text_hash == s2.winner_text_hash

    def test_different_sessions_produce_different_signatures(self) -> None:
        # Replay defence: the SAME candidates under different session_ids
        # must produce different signatures.  This is the property that
        # prevents a t-1 attacker from replaying a captured honest signature
        # into a fresh adjudication.
        judges, priv = _build_judges(1)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=1)

        candidates = _consensus_candidates()
        r1 = ffja.adjudicate(candidates, priv, session_id="session-A")
        r2 = ffja.adjudicate(candidates, priv, session_id="session-B")

        assert r1.judge_signatures[0].signature != r2.judge_signatures[0].signature
        # but coalition-level outcome is identical
        assert r1.agreed is True and r2.agreed is True
        assert r1.winner_agent_id == r2.winner_agent_id


# =============================================================================
# Parallel execution
# =============================================================================


class TestParallelism:
    def test_parallel_execution_actually_parallel(self) -> None:
        # 4 judges, each with a 200 ms embed() sleep, 3 candidates each.
        # Sequential lower bound would be 4 * 3 * 0.2 = 2.4 s.
        # Parallel (max_workers=4) should finish well under 1.6 s.
        judges, priv = _build_judges(4, sleep_s=0.2)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3, max_workers=4)

        start = time.perf_counter()
        result = ffja.adjudicate(_consensus_candidates(), priv)
        elapsed = time.perf_counter() - start

        assert result.agreed is True
        # Budget: generous upper bound accounting for GIL + thread overhead.
        assert elapsed < 1.6, f"parallel adjudication too slow: {elapsed:.3f}s"


# =============================================================================
# Structural sanity — to_audit_dict is json-safe
# =============================================================================


class TestAuditDict:
    def test_to_audit_dict_is_json_safe(self) -> None:
        import json

        judges, priv = _build_judges(4)
        ffja = FederatedJudgeAnchor(judges=judges, threshold=3)
        result = ffja.adjudicate(_consensus_candidates(), priv)
        audit = result.to_audit_dict()
        # Round-trip must succeed.
        encoded = json.dumps(audit, sort_keys=True)
        assert "judge_signatures" in encoded
        assert "constitutional_hash" in encoded


# =============================================================================
# Typing check — judge_private_keys param should accept Mapping
# =============================================================================


def test_mapping_type_accepted() -> None:
    judges, priv = _build_judges(2)
    ffja = FederatedJudgeAnchor(judges=judges, threshold=2)
    # Just a static-style assertion that Mapping works.
    mapping: Mapping[str, bytes] = priv
    result = ffja.adjudicate(_consensus_candidates(), mapping)
    assert result.num_judges == 2
