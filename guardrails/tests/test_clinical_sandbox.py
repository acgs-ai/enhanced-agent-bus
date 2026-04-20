"""Tests for clinical sandbox profiles.

Constitutional Hash: 608508a9bd224290
"""

from collections.abc import Callable

import pytest

from enhanced_agent_bus.guardrails.sandbox_providers import (
    ClinicalSandboxProfile,
    DockerSandboxProvider,
    SandboxExecutionRequest,
    generate_clinical_seccomp_profile,
)

# ---------------------------------------------------------------------------
# Built-in profile defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("profile_factory", "attribute", "expected", "check"),
    [
        (ClinicalSandboxProfile.phi_processing, "profile_name", "phi_processing", "equals"),
        (ClinicalSandboxProfile.phi_processing, "allowed_network_endpoints", [], "equals"),
        (ClinicalSandboxProfile.phi_processing, "allowed_outbound_ports", [], "equals"),
        (ClinicalSandboxProfile.phi_processing, "audit_all_syscalls", True, "equals"),
        (ClinicalSandboxProfile.phi_processing, "require_fips_crypto", True, "equals"),
        (ClinicalSandboxProfile.phi_processing, "gpu_passthrough", False, "equals"),
        (ClinicalSandboxProfile.phi_processing, "data_classification", "phi", "equals"),
        (
            ClinicalSandboxProfile.clinical_inference,
            "profile_name",
            "clinical_inference",
            "equals",
        ),
        (ClinicalSandboxProfile.clinical_inference, "gpu_passthrough", True, "equals"),
        (
            ClinicalSandboxProfile.clinical_inference,
            "allowed_network_endpoints",
            "fhir.endpoint.local",
            "contains",
        ),
        (ClinicalSandboxProfile.clinical_inference, "allowed_outbound_ports", [443], "equals"),
        (ClinicalSandboxProfile.clinical_inference, "data_classification", "phi", "equals"),
        (ClinicalSandboxProfile.research_compute, "profile_name", "research_compute", "equals"),
        (ClinicalSandboxProfile.research_compute, "gpu_passthrough", True, "equals"),
        (ClinicalSandboxProfile.research_compute, "max_phi_memory_mb", 2048, "equals"),
        (
            ClinicalSandboxProfile.research_compute,
            "data_classification",
            "de-identified",
            "equals",
        ),
        (ClinicalSandboxProfile.de_identified, "profile_name", "de_identified", "equals"),
        (ClinicalSandboxProfile.de_identified, "gpu_passthrough", False, "equals"),
        (ClinicalSandboxProfile.de_identified, "require_fips_crypto", False, "equals"),
        (
            ClinicalSandboxProfile.de_identified,
            "data_classification",
            "de-identified",
            "equals",
        ),
        (ClinicalSandboxProfile.de_identified, "allowed_outbound_ports", 80, "contains"),
        (ClinicalSandboxProfile.de_identified, "allowed_outbound_ports", 443, "contains"),
    ],
)
def test_builtin_profile_defaults(
    profile_factory: Callable[[], ClinicalSandboxProfile],
    attribute: str,
    expected: object,
    check: str,
) -> None:
    profile = profile_factory()
    actual = getattr(profile, attribute)
    if check == "contains":
        assert expected in actual
    else:
        assert actual == expected


# ---------------------------------------------------------------------------
# PHI volume safety
# ---------------------------------------------------------------------------


class TestPHIVolumeSafety:
    """PHI volumes must always be mounted read-only."""

    def test_phi_volumes_read_only(self) -> None:
        profile = ClinicalSandboxProfile(
            profile_name="test_phi",
            phi_volume_paths=["/data/phi", "/data/records"],
            data_classification="phi",
        )
        request = SandboxExecutionRequest(
            code="x = 1",
            data={},
            context={},
        )
        provider = DockerSandboxProvider()
        config = provider._build_clinical_container_config(
            profile, request, "/tmp/host", "test-container", "/tmp/seccomp.json"
        )
        volumes = config["volumes"]
        assert isinstance(volumes, dict)
        for phi_path in profile.phi_volume_paths:
            assert phi_path in volumes
            vol_config = volumes[phi_path]
            assert "ro" in vol_config["mode"]
            assert "noexec" in vol_config["mode"]


# ---------------------------------------------------------------------------
# Seccomp profile generation
# ---------------------------------------------------------------------------


class TestSeccompGeneration:
    """Tests for generate_clinical_seccomp_profile."""

    def test_default_action(self) -> None:
        profile = ClinicalSandboxProfile.phi_processing()
        seccomp = generate_clinical_seccomp_profile(profile)
        assert seccomp["defaultAction"] == "SCMP_ACT_ERRNO"

    def test_audit_mode_uses_log(self) -> None:
        profile = ClinicalSandboxProfile.phi_processing()
        assert profile.audit_all_syscalls is True
        seccomp = generate_clinical_seccomp_profile(profile)
        syscalls = seccomp["syscalls"]
        assert isinstance(syscalls, list)
        assert syscalls[0]["action"] == "SCMP_ACT_LOG"

    def test_non_audit_mode_uses_allow(self) -> None:
        profile = ClinicalSandboxProfile.de_identified()
        assert profile.audit_all_syscalls is False
        seccomp = generate_clinical_seccomp_profile(profile)
        syscalls = seccomp["syscalls"]
        assert isinstance(syscalls, list)
        assert syscalls[0]["action"] == "SCMP_ACT_ALLOW"

    def test_base_syscalls_present(self) -> None:
        profile = ClinicalSandboxProfile.de_identified()
        seccomp = generate_clinical_seccomp_profile(profile)
        names = seccomp["syscalls"][0]["names"]
        for expected in ("read", "write", "open", "close", "mmap", "mprotect"):
            assert expected in names

    def test_architectures(self) -> None:
        profile = ClinicalSandboxProfile.de_identified()
        seccomp = generate_clinical_seccomp_profile(profile)
        assert "SCMP_ARCH_X86_64" in seccomp["architectures"]


# ---------------------------------------------------------------------------
# Network isolation
# ---------------------------------------------------------------------------


class TestNetworkIsolation:
    """Network isolation for phi_processing profile."""

    def test_phi_processing_network_none(self) -> None:
        profile = ClinicalSandboxProfile.phi_processing()
        request = SandboxExecutionRequest(code="x = 1", data={}, context={})
        provider = DockerSandboxProvider()
        config = provider._build_clinical_container_config(
            profile, request, "/tmp/host", "test-net", "/tmp/seccomp.json"
        )
        assert config["network_mode"] == "none"

    def test_research_compute_network_bridge(self) -> None:
        profile = ClinicalSandboxProfile.research_compute()
        request = SandboxExecutionRequest(code="x = 1", data={}, context={})
        provider = DockerSandboxProvider()
        config = provider._build_clinical_container_config(
            profile, request, "/tmp/host", "test-net", "/tmp/seccomp.json"
        )
        assert config["network_mode"] == "bridge"


# ---------------------------------------------------------------------------
# GPU configuration
# ---------------------------------------------------------------------------


class TestGPUConfig:
    """GPU passthrough for clinical_inference profile."""

    def test_clinical_inference_gpu_requested(self) -> None:
        profile = ClinicalSandboxProfile.clinical_inference()
        request = SandboxExecutionRequest(code="x = 1", data={}, context={})
        provider = DockerSandboxProvider()
        config = provider._build_clinical_container_config(
            profile, request, "/tmp/host", "test-gpu", "/tmp/seccomp.json"
        )
        assert "device_requests" in config
        device_requests = config["device_requests"]
        assert isinstance(device_requests, list)
        assert len(device_requests) == 1
        assert device_requests[0]["Driver"] == "nvidia"

    def test_phi_processing_no_gpu(self) -> None:
        profile = ClinicalSandboxProfile.phi_processing()
        request = SandboxExecutionRequest(code="x = 1", data={}, context={})
        provider = DockerSandboxProvider()
        config = provider._build_clinical_container_config(
            profile, request, "/tmp/host", "test-gpu", "/tmp/seccomp.json"
        )
        assert "device_requests" not in config
