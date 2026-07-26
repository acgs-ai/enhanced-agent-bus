"""Conformance gates for the standalone extraction.

These tests are ratchets: each records the known-bad set in a checked-in
allowlist and asserts the observed set is a subset of it. Remediation phases
delete lines from the allowlists; a module or shim that regresses into a gap
fails the build.
"""
