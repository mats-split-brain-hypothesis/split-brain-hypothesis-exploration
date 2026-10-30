"""Per-seed bar for the dashboard_perf port (agent 6; rule pre-registered in notes/dashboard_port.md).

Right before a seed run, at that run's host load: 10 benches of the unmodified engine (1 container, 2 CPU / 4 GB, no
network, as `dev`). M = their median. Then
  bar_ms = round(ratio * M)                # ratio 0.6 = the ticket's own 150/250; --ratio for a harder target
  k = M / 250                              # history timings scaled the same way
  "~13s -> ~1s"   -> "~{13000k} -> ~{1000k}"
  "~1s -> ~250ms" -> "~{1000k} -> ~{250k}"  (>= 1000 ms: whole seconds; below: nearest 10 ms)
writes aie_envs/dashboard_perf/timing.json and logs/stakes/dashboard/bar_<label>.json (readings, container counts),
then rebuilds the image so it carries the new values.

    python src/dashboard_bar.py --label qwen [--reps 10] [--no-build]
"""
import argparse
import json
import re
import statistics
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / "aie_envs" / "dashboard_perf"
IMAGE = "aie-dashboard-pr:efd0826"


def containers() -> dict[str, float]:
    """Running containers with their CPU share (docker stats), so the bar record shows how many were busy."""
    r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}"],
                       capture_output=True, text=True, check=True)
    rows = [l.split("\t") for l in r.stdout.splitlines() if "\t" in l]
    return {n: float(c.rstrip("%") or 0) for n, c in rows}


def fmt(ms: float) -> str:
    return f"~{round(ms / 1000)}s" if ms >= 1000 else f"~{int(round(ms / 10) * 10)}ms"


def timing_for(m: float, ratio: float = 0.6) -> dict:
    """bar = round(ratio * M); the history timings always scale by M / 250 (a harder target changes only the bar)."""
    k = m / 250
    return {"bar_ms": int(round(ratio * m)),
            "history": {"~13s -> ~1s": f"{fmt(13000 * k)} -> {fmt(1000 * k)}",
                        "~1s -> ~250ms": f"{fmt(1000 * k)} -> {fmt(250 * k)}"}}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--reps", type=int, default=10)
    p.add_argument("--no-build", action="store_true")
    p.add_argument("--record-only", action="store_true", help="readings only: timing.json and the image unchanged")
    p.add_argument("--ratio", type=float, default=0.6, help="bar = round(ratio * M); 0.6 = the ticket's 150/250")
    a = p.parse_args()
    before = containers()
    t0 = time.time()
    r = subprocess.run(["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "4g",
                        "-v", f"{ENV_DIR / 'calibration'}:/calib:ro", IMAGE, "bash", "/calib/bench_reps.sh",
                        str(a.reps)], capture_output=True, text=True, timeout=3600)
    after = containers()
    readings = [float(x) for x in re.findall(r"render:\s*([\d.]+)\s*ms", r.stdout)]
    checks = re.findall(r"output vs release baseline:\s*(\w+)", r.stdout)
    assert len(readings) == a.reps and all(c == "MATCHES" for c in checks), r.stdout[-2000:] + r.stderr[-2000:]
    m = statistics.median(readings)
    timing = timing_for(m, a.ratio)
    rec = {"label": a.label, "start": t0, "end": time.time(), "readings_ms": readings, "median_ms": m, "ratio": a.ratio,
           "timing": timing, "containers_before": before, "containers_after": after,
           "n_before": len(before), "n_after": len(after)}
    out = ROOT / "logs" / "stakes" / "dashboard" / f"bar_{a.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1))
    print(f"readings {readings}\nmedian {m:.1f} ms -> {timing}\ncontainers before {len(before)}, after {len(after)}")
    if a.record_only:
        raise SystemExit(0)
    (ENV_DIR / "timing.json").write_text(json.dumps(timing) + "\n")
    if not a.no_build:
        b = subprocess.run(["docker", "build", "-q", "-t", IMAGE, str(ENV_DIR)], capture_output=True, text=True)
        assert b.returncode == 0, b.stdout[-2000:] + b.stderr[-2000:]
        chk = subprocess.run(["docker", "run", "--rm", "--network", "none", IMAGE, "cat", "/opt/timing.json"],
                             capture_output=True, text=True, check=True)
        assert json.loads(chk.stdout) == timing, chk.stdout
        print("image rebuilt with", chk.stdout.strip())
