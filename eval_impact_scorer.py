import os
import re
import subprocess
import sys


def get_p99():
    # Ensure packages root is in PYTHONPATH
    pkg_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["PYTHONPATH"] = pkg_path + ":" + env.get("PYTHONPATH", "")

    cmd = [sys.executable, "-m", "enhanced_agent_bus.profiling.benchmark_gpu_decision", "--samples", "50", "--no-save"]
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        # Search for Latency P99 in the output (it might be in a JSON message field)
        # Example: "message": "  Latency P99: 103.628ms"
        matches = re.findall(r"Latency P99: ([\d.]+)ms", result.stdout + result.stderr)
        if matches:
            return float(matches[-1])

        # Fallback: check for sequential RPS if latency not found
        rps_matches = re.findall(r"Sequential: [\d.]+s, ([\d.]+) RPS", result.stdout + result.stderr)
        if rps_matches:
            rps = float(rps_matches[-1])
            if rps > 0:
                return 1000.0 / rps

    except Exception as e:
        print(f"Error running benchmark: {e}", file=sys.stderr)

    return 9999.0

if __name__ == "__main__":
    print(f"latency_p99_ms: {get_p99():.3f}")
