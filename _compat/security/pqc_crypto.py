"""Shim for src.core.shared.security.pqc_crypto."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

try:
    from src.core.shared.security.pqc_crypto import *  # noqa: F403
except ImportError:
    PQC_CRYPTO_AVAILABLE = False

    @runtime_checkable
    class PQCKeyPair(Protocol):
        public_key: bytes
        private_key: bytes

    @runtime_checkable
    class PQCCryptoProvider(Protocol):
        def generate_keypair(self) -> PQCKeyPair: ...
        def sign(self, data: bytes, private_key: bytes) -> bytes: ...
        def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool: ...
        def encrypt(self, data: bytes, public_key: bytes) -> bytes: ...
        def decrypt(self, data: bytes, private_key: bytes) -> bytes: ...

    class StubPQCKeyPair:
        def __init__(self) -> None:
            self.public_key = b""
            self.private_key = b""

    class StubPQCCryptoProvider:
        def generate_keypair(self) -> StubPQCKeyPair:
            return StubPQCKeyPair()

        def sign(self, data: bytes, private_key: bytes) -> bytes:
            return b""

        def verify(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
            return False

        def encrypt(self, data: bytes, public_key: bytes) -> bytes:
            return data

        def decrypt(self, data: bytes, private_key: bytes) -> bytes:
            return data

    @dataclass
    class PQCConfig:
        """Fallback PQC configuration used when the shared crypto package is absent."""

        pqc_enabled: bool = False
        pqc_mode: str = "classical_only"
        verification_mode: str = "strict"
        kem_algorithm: str = "kyber768"
        migration_phase: str = "phase_0"
        cache_max_size: int = 1000
        enforce_content_hash: bool = True

        def validate(self) -> list[str]:
            return []

    class PQCCryptoService:
        """Import-only fallback for the real PQC service.

        The fallback deliberately does not accept runtime configuration. Callers
        that try to use PQC while the real service is unavailable fail closed via
        the existing TypeError handling in the validation path.
        """

        config: PQCConfig

    @dataclass
    class _SignatureComponent:
        algorithm: str | None = None
        signature: bytes = b""

        @classmethod
        def from_value(cls, value: object) -> "_SignatureComponent | None":
            if value is None:
                return None
            if isinstance(value, cls):
                return value
            if isinstance(value, dict):
                raw_signature = value.get("signature", b"")
                if isinstance(raw_signature, str):
                    signature = raw_signature.encode("utf-8")
                elif isinstance(raw_signature, bytes):
                    signature = raw_signature
                else:
                    signature = b""
                algorithm = value.get("algorithm")
                return cls(
                    algorithm=str(algorithm) if algorithm is not None else None,
                    signature=signature,
                )
            return None

    @dataclass
    class HybridSignature:
        """Fallback hybrid signature container for import-compatible tests."""

        content_hash: str = ""
        constitutional_hash: str = ""
        classical: _SignatureComponent | None = None
        pqc: _SignatureComponent | None = None

        @classmethod
        def from_dict(cls, data: dict[str, object]) -> "HybridSignature":
            return cls(
                content_hash=str(data.get("content_hash", "")),
                constitutional_hash=str(data.get("constitutional_hash", "")),
                classical=_SignatureComponent.from_value(data.get("classical")),
                pqc=_SignatureComponent.from_value(data.get("pqc")),
            )

    @dataclass
    class PQCMetadata:
        """Fallback PQC validation metadata."""

        pqc_enabled: bool = False
        pqc_algorithm: str | None = None
        classical_verified: bool = False
        pqc_verified: bool = False
        verification_mode: str = "classical_only"

    @dataclass
    class ValidationResult:
        """Fallback PQC validation result."""

        valid: bool = False
        constitutional_hash: str = ""
        errors: list[str] = field(default_factory=list)
        warnings: list[str] = field(default_factory=list)
        pqc_metadata: PQCMetadata | None = None
        hybrid_signature: HybridSignature | None = None
        validation_duration_ms: float | None = None
        classical_verification_ms: float | None = None
        pqc_verification_ms: float | None = None

    def get_pqc_provider(**kwargs: Any) -> StubPQCCryptoProvider:
        _ = kwargs
        return StubPQCCryptoProvider()

    def generate_key_pair(algorithm_variant: object) -> tuple[bytes, bytes]:
        _ = algorithm_variant
        raise RuntimeError("PQC crypto provider is unavailable")

    def verify_signature(
        algorithm_variant: object,
        public_key_bytes: bytes,
        message: bytes,
        signature: bytes,
    ) -> bool:
        _ = (algorithm_variant, public_key_bytes, message, signature)
        return False
