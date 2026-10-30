"""Fetch Terminal-Bench job metadata and trajectories from the Harbor Hub (hub.harborframework.com).

  python src/tb_hub.py trials <job_id> <out.jsonl>          # one row per trial: task, reward, tokens, cost, status
  python src/tb_hub.py traj <job_id> <trial_id> <out.json>  # one ATIF trajectory
  python src/tb_hub.py pickall <trials.jsonl> <picks.json>   # every trial with output, for fetch
  python src/tb_hub.py fetch <job_id> <picks.json> <dir>     # download picked trajectories (skips existing)

The job page is a Next.js page whose server payload embeds the trial list, 100 per page (?page=N).
Hub jobs state no licence: keep downloads under logs/ (not in git).
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

HUB = "https://hub.harborframework.com"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; split-brain-hypothesis)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode()


def payload(html: str) -> str:
    """Concatenate the decoded self.__next_f.push([1, "..."]) strings."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    return "".join(json.loads(p) for p in parts)


def objects_with(text: str, key: str):
    """Yield every JSON object in text that starts with {"id":..., "config_values" and contains key."""
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{"id":"[0-9a-f-]{36}","config_values"', text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except json.JSONDecodeError:
            continue
        if key in obj:
            yield obj


def trials(job: str) -> list[dict]:
    rows, page = {}, 1
    while True:
        text = payload(get(f"{HUB}/jobs/{job}?page={page}"))
        found = list(objects_with(text, "task_name"))
        new = [o for o in found if o["id"] not in rows]
        for o in new:
            rows[o["id"]] = o
        m = re.search(r'"total_pages":(\d+)', text)
        total_pages = int(m.group(1)) if m else page
        print(f"page {page}/{total_pages}: {len(found)} trials, {len(new)} new", file=sys.stderr)
        if page >= total_pages or not new:
            break
        page += 1
    return list(rows.values())


def first_user_message(job: str, trial: str, chunk: int = 65536, max_bytes: int = 2_000_000) -> str:
    """The task instruction (step 1's message), reading only the start of trajectory.json."""
    url = f"{HUB}/api/trials/{trial}/files/agent/trajectory.json?jobId={job}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; split-brain-hypothesis)"})
    buf = b""
    with urllib.request.urlopen(req, timeout=120) as r:
        while len(buf) < max_bytes:
            data = r.read(chunk)
            if not data:
                break
            buf += data
            text = buf.decode(errors="ignore")
            m = re.search(r'"source":\s*"user",\s*"message":\s*', text)
            if m:
                try:
                    msg, _ = json.JSONDecoder().raw_decode(text, m.end())
                    return msg if isinstance(msg, str) else json.dumps(msg)
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"no user message in the first {len(buf)} bytes of {trial}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "instructions":
        # One instruction per task, from the first trial of each task that has a trajectory.
        job, trials_path, out_path = sys.argv[2:5]
        rows = [json.loads(l) for l in open(trials_path)]
        done = set()
        try:
            done = {json.loads(l)["task_name"] for l in open(out_path)}
        except FileNotFoundError:
            pass
        with open(out_path, "a") as f:
            for task in sorted({r["task_name"] for r in rows} - done):
                for r in [r for r in rows if r["task_name"] == task]:
                    try:
                        msg = first_user_message(job, r["id"])
                    except Exception as e:  # noqa: BLE001
                        print(task, r["id"], "failed:", e, file=sys.stderr)
                        continue
                    f.write(json.dumps({"task_name": task, "trial_id": r["id"], "instruction": msg}) + "\n")
                    f.flush()
                    print(task, len(msg), file=sys.stderr)
                    break
    if cmd == "trials":
        out = trials(sys.argv[2])
        with open(sys.argv[3], "w") as f:
            for o in out:
                f.write(json.dumps(o) + "\n")
        print(len(out), "trials")
    elif cmd == "traj":
        job, trial, path = sys.argv[2:5]
        txt = get(f"{HUB}/api/trials/{trial}/trajectory?jobId={job}")
        with open(path, "w") as f:
            f.write(txt)
        print(path, len(txt))
    elif cmd == "pick":
        # Two trials per task for the given tasks: one passed and one failed where both exist, else the first two
        # by trial id. Errored trials with no output tokens have no trajectory and are skipped.
        trials_path, tasks_csv, out_path = sys.argv[2:5]
        rows = [json.loads(l) for l in open(trials_path)]
        picks = []
        for task in tasks_csv.split(","):
            ts = sorted([r for r in rows if r["task_name"].split("/")[-1] == task and (r["output_tokens"] or 0) > 0],
                        key=lambda r: r["id"])
            passed = [r for r in ts if (r["reward"] or 0) >= 1]
            failed = [r for r in ts if (r["reward"] or 0) < 1]
            chosen = [passed[0], failed[0]] if passed and failed else ts[:2]
            picks += [{"task": task, "trial_id": r["id"], "trial_name": r["name"], "reward": r["reward"],
                       "error_type": r["error_type"]} for r in chosen]
        existing = json.load(open(out_path)) if Path(out_path).exists() else []
        seen = {p["trial_id"] for p in existing}
        existing += [p for p in picks if p["trial_id"] not in seen]
        Path(out_path).write_text(json.dumps(existing, indent=1))
        print(len(existing), "picked trials in", out_path)
    elif cmd == "pickall":
        # Every trial with output tokens (errored trials without output have no trajectory).
        trials_path, out_path = sys.argv[2:4]
        rows = [json.loads(l) for l in open(trials_path)]
        picks = [{"task": r["task_name"].split("/")[-1], "trial_id": r["id"], "trial_name": r["name"],
                  "reward": r["reward"], "error_type": r["error_type"]} for r in rows if (r["output_tokens"] or 0) > 0]
        Path(out_path).write_text(json.dumps(picks, indent=1))
        print(len(picks), "trials in", out_path)
    elif cmd == "fetch":
        # Download the picked trajectories into <dir>/<trial_name>.json, skipping ones already there.
        job, picks_path, out_dir = sys.argv[2:5]
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for p in json.load(open(picks_path)):
            path = Path(out_dir) / f"{p['trial_name']}.json"
            if path.exists():
                continue
            try:
                txt = get(f"{HUB}/api/trials/{p['trial_id']}/trajectory?jobId={job}")
                path.write_text(txt)
                print(p["trial_name"], f"{len(txt) / 1e6:.1f} MB", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                print(p["trial_name"], "failed:", e, file=sys.stderr)
