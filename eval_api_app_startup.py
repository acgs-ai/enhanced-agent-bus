"""Eval for api-app-startup autoresearch loop.

Measures median cold-start import latency of enhanced_agent_bus.api.app
over 3 subprocess runs.
Outputs: api_app_startup_ms: <float>

Fixed eval — do not modify once the loop begins.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys

_WT = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.join(os.path.dirname(_WT), "api-app-pkg")

_BOOTSTRAP = (
    "import sys, importlib; "
    "sys.meta_path = [f for f in sys.meta_path if type(f).__name__ != 'DistutilsMetaFinder']; "
    f"sys.path = ['{_PKG}'] + [p for p in sys.path if '/Documents/' not in p]; "
    "importlib.invalidate_caches(); "
)

_CODE = (
    _BOOTSTRAP
    + "import time; t = time.perf_counter(); "
    "import enhanced_agent_bus.api.app; "
    "print((time.perf_counter()-t)*1000)"
)

env = os.environ.copy()
env["PYTHONPATH"] = _PKG

samples: list[float] = []
for _ in range(3):
    cp = subprocess.run(
        [sys.executable, "-c", _CODE],
        cwd=_WT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    samples.append(float(cp.stdout.strip().splitlines()[-1]))

result = statistics.median(samples)
print(f"api_app_startup_ms: {result:.3f}")
