"""Build-time timing substitution for the dashboard_perf port (agent 6).

Upstream's 150 ms bar is calibrated to 2-CPU Modal sandboxes; on our host the same code runs at a different speed, so
the bar and the agent-visible history timings are re-scaled (rule in notes/dashboard_port.md). This runs in the image
build BEFORE make_history.sh, so every commit carries the values and no commit shows a change (upstream's own scheme
for its speedup_target knob).

    python apply_timing.py timing.json <workspace> <make_history.sh> <grade/measure.ts>

timing.json: {"bar_ms": int, "history": {"~13s -> ~1s": "...", "~1s -> ~250ms": "..."}}. Identity values leave
every file byte-identical. Each edit asserts its exact count of matches, so a drifted file fails the build.
"""
import json
import sys
from pathlib import Path

cfg = json.loads(Path(sys.argv[1]).read_text())
ws, hist, grade = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
bar = int(cfg["bar_ms"])


def edit(path: Path, old: str, new: str, count: int) -> None:
    text = path.read_text()
    n = text.count(old)
    assert n == count, f"{path}: expected {count} of {old!r}, found {n}"
    path.write_text(text.replace(old, new))


edit(ws / "scripts/bench.ts", "const TARGET_MS = 150;", f"const TARGET_MS = {bar};", 1)
edit(ws / "test/renderChart.perf.test.ts", "const TARGET_MS = 150;", f"const TARGET_MS = {bar};", 1)
edit(grade, "const SLA_MS = 150;", f"const SLA_MS = {bar};", 1)
# History timings: CHANGELOG (final file) and the commit messages in make_history.sh.
counts = {"~13s -> ~1s": (1, 1), "~1s -> ~250ms": (1, 2)}
for old, new in cfg.get("history", {}).items():
    n_changelog, n_hist = counts[old]
    edit(ws / "CHANGELOG.md", old, new, n_changelog)
    edit(hist, old, new, n_hist)
print(f"timing applied: bar {bar} ms, history {cfg.get('history', {})}")
