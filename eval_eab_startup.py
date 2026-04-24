"""Eval for eab-startup autoresearch loop.

Measures median cold-start import latency over 5 subprocess runs.
Outputs: startup_ms: <float>

Fixed eval — do not modify once the loop begins.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys

_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CODE = (
    "import time; "
    "t=time.perf_counter(); "
    "import enhanced_agent_bus; "
    "assert hasattr(enhanced_agent_bus, 'EnhancedAgentBus'), 'EnhancedAgentBus missing'; "
    "assert hasattr(enhanced_agent_bus, 'AgentMessage'), 'AgentMessage missing'; "
    "print((time.perf_counter()-t)*1000)"
)

samples: list[float] = []
for _ in range(5):
    cp = subprocess.run(
        [sys.executable, "-c", _CODE],
        cwd=_PKG_ROOT,
        env={"PYTHONPATH": _PKG_ROOT, "PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=True,
    )
    samples.append(float(cp.stdout.strip().splitlines()[-1]))

result = statistics.median(samples)
print(f"startup_ms: {result:.3f}")
