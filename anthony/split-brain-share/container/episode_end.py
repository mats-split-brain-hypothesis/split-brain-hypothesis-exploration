"""How a run ended, from its records: agent (the model finished), api_error, content_filter (the provider's input
moderation, e.g. Alibaba's data_inspection_failed), time_cap (the --hours stop), killed (stopped some other way, or the
launcher died), launch_failed (no stream). Rates should count agent-ended runs only; the others are censored.

    python3 episode_end.py RUN_DIR [...]          # prints one line per run
    python3 episode_end.py --write RUN_DIR        # also adds episode_end / episode_end_detail to meta.json (launch.sh)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

CAP_SLACK_S = 180  # docker stop -t 60 plus the bundle and meta writes


def classify(run: Path) -> tuple[str, str]:
    meta = json.loads((run / "meta.json").read_text())
    stream = run / "stream.jsonl"
    if not stream.exists() or stream.stat().st_size == 0:
        return "launch_failed", "no stream output"
    result = None
    for line in stream.open():
        if '"type":"result"' in line:
            result = json.loads(line)
    if result is not None:
        text = str(result.get("result", ""))[:300]
        if result.get("terminal_reason") == "api_error" or (result.get("is_error") and text.startswith("API Error")):
            return ("content_filter" if "data_inspection_failed" in text else "api_error"), text
        return "agent", result.get("terminal_reason") or result.get("subtype") or ""
    hours = meta.get("hours")
    if meta.get("start") and meta.get("end") and hours is not None:
        dur = (datetime.fromisoformat(meta["end"]) - datetime.fromisoformat(meta["start"])).total_seconds()
        if dur >= float(hours) * 3600 - CAP_SLACK_S:
            return "time_cap", f"{dur / 3600:.2f} h of {hours}"
    return "killed", f"exit {meta.get('exit_code')}, no result event"


def main() -> None:
    args = sys.argv[1:]
    write = "--write" in args
    for a in (x for x in args if x != "--write"):
        run = Path(a)
        end, detail = classify(run)
        print(f"{run.name:32} {end:15} {detail[:120]}")
        if write:
            m = run / "meta.json"
            meta = json.loads(m.read_text())
            meta.update(episode_end=end, episode_end_detail=detail)
            tmp = m.with_suffix(".tmp")
            tmp.write_text(json.dumps(meta, indent=2) + "\n")
            tmp.replace(m)


if __name__ == "__main__":
    main()
