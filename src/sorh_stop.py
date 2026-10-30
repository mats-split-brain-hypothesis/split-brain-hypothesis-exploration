"""Stop one registered School of Reward Hacks runner by its PID (orchestrator, 2026-10-23).

  .venv/bin/python src/sorh_stop.py <pid> [--config monitor/sorh_runs.json]

Refuses unless <pid> is a run in the monitor config and its command line still contains that run's cmd_contains.
Then, via src/sorh_monitor.py's stop_run: copies the runner's stdout to logs/sorh_monitor/, sends SIGINT, waits 60 s,
and sends SIGTERM only if the process is still alive (a runner started as `nohup ... &` from a non-interactive shell
ignores SIGINT). Nothing stronger. The action is logged in logs/sorh_monitor/alerts.jsonl.
Use only after a stop rule fired and a person (agent 2) has looked; never restart anything from here.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_monitor as M  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pid", type=int)
    ap.add_argument("--config", default=str(M.ROOT / "monitor" / "sorh_runs.json"))
    a = ap.parse_args()
    runs = [r for r in json.loads(Path(a.config).read_text())["runs"] if r.get("pid") == a.pid]
    if len(runs) != 1:
        sys.exit(f"refusing: PID {a.pid} is not exactly one registered SoRH run in {a.config} ({len(runs)} matches)")
    sys.exit(0 if M.stop_run(a.config, runs[0]["name"]) else 1)
