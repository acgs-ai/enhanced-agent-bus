# Contributing

This package is a governance runtime. Treat changes as security-sensitive.

Required contribution posture:

- Do not add production fallbacks without routing the decision through `api/runtime_profile.py`.
- Do not trust caller-provided governance metadata.
- Do not mutate governance state without a receipt or audit trail.
- Keep tenant isolation checks explicit.
- Update `docs/security/route-security-matrix.md` when adding or changing routes.
- Add or update `tests/critical_path/` when changing auth, tenant isolation, governance approval, receipt verification, runtime startup, or audit behavior.

Before submitting:

```bash
python -m ruff check <changed-python-files>
python -m py_compile <changed-python-files>
python -m pytest tests/critical_path -q --import-mode=importlib
git diff --check
```
