"""The API half of the resamples (RESAMPLE.md, extension; Anthony 2026-10-24: all six DeepSeek runs with credit planned
then lost): resend the exact request that produced a run's first contribution.md write (rebuild.py's requests, from
Claude Code's session log) N times and keep each reply. Reply-boundary cut only: the model regenerates the whole
write reply (thinking included) from the same history.

    python3 resample_api.py RUN [--n 10] [--port 8911] [--workers 3] [--dry]

Goes through a local container/api_proxy.py (it holds the key, pins the provider, strips nothing this request has):
    python3 container/api_proxy.py --listen 127.0.0.1:8911 --key-file ~/j-lens-mean/umot/.env --provider alibaba \\
        --model deepseek/deepseek-v4-pro-0813 --log whitebox/out/api-resample.jsonl
Writes out/RUN/resample/api.jsonl (one line per sample: content blocks, the contribution text it writes if any,
usage, seconds; a rerun with a larger --n tops up) and out/RUN/resample/api-orig.json (request index, the original
reply, its input tokens from the run's api.jsonl to compare with the resamples').
"""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import rebuild  # noqa: E402


def contribution(resp: dict) -> tuple[str | None, str | None]:
    """(tool, text) of the reply's write to contribution.md: Write content, Edit new_string, or a Bash heredoc."""
    for c in resp.get("content", []):
        if c.get("type") != "tool_use":
            continue
        i = c.get("input") or {}
        if str(i.get("file_path", "")).endswith("contribution.md"):
            return c["name"], i.get("content", i.get("new_string"))
        cmd = str(i.get("command", ""))
        if "contribution.md" in cmd and ("<<" in cmd or "cat >" in cmd or "tee " in cmd):
            return c["name"], cmd
    return None, None


def find_write(reqs: list[dict]) -> tuple[int, dict]:
    for k in range(len(reqs) - 1):
        n = len(reqs[k]["messages"])
        if len(reqs[k + 1]["messages"]) <= n or reqs[k + 1]["messages"][:n] != reqs[k]["messages"]:
            continue  # not extended by a reply (a retried request, or a compaction)
        resp = reqs[k + 1]["messages"][n]
        if contribution(resp)[0]:
            return k, resp
    raise SystemExit("no contribution.md write found")


def body(req: dict) -> dict:
    p = req["params"]
    msgs = [{k: v for k, v in m.items() if not k.startswith("_")} for m in req["messages"]]
    b = {"model": p["model"], "system": req["system"], "tools": req["tools"], "messages": msgs,
         "max_tokens": p["max_tokens"]}
    for k in ("thinking", "context_management", "output_config", "temperature", "tool_choice", "metadata"):
        if k in p:
            b[k] = p[k]
    return b


def call(port: int, b: dict, betas: list[str]) -> dict:
    data = json.dumps(b).encode()
    for attempt in range(5):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/messages", data,
                                     {"content-type": "application/json", "anthropic-version": "2023-06-01",
                                      "anthropic-beta": ",".join(betas), "x-api-key": "via-proxy"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=1800).read())
        except urllib.error.HTTPError as e:  # 529: the proxy found the generation incomplete (a resample is fine)
            if e.code not in (429, 500, 502, 503, 529) or attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
        except (urllib.error.URLError, ConnectionError, TimeoutError):  # a reset connection to the local proxy
            if attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--port", type=int, default=8911)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    reqs = rebuild.requests(rebuild.load(a.run))
    k, orig = find_write(reqs)
    req = reqs[k]
    api = [json.loads(l) for l in (rebuild.SB / "runs" / a.run / "api.jsonl").open()]
    posts = [x for x in api if x.get("method") == "POST" and x.get("msgs") == len(req["messages"]) and x.get("status") == 200]
    out = HERE / "out" / a.run / "resample"
    out.mkdir(parents=True, exist_ok=True)
    tool, text = contribution(orig)
    (out / "api-orig.json").write_text(json.dumps({
        "run": a.run, "request": k, "of": len(reqs), "timestamp": req["timestamp"], "messages": len(req["messages"]),
        "filled": sum(1 for m in req["messages"] if m.get("_filled")), "params": req["params"],
        "orig_in_tokens": [x.get("in_tokens") for x in posts], "orig_reply": orig, "orig_tool": tool,
        "orig_contribution": text}, indent=1))
    print(f"{a.run}: request {k} of {len(reqs)} ({req['timestamp']}), {len(req['messages'])} messages; original "
          f"input tokens {[x.get('in_tokens') for x in posts]}; original write {tool}, {len(text or '')} chars")
    if a.dry:
        return
    f = out / "api.jsonl"
    have = sum(1 for _ in f.open()) if f.exists() else 0
    b, lock = body(req), threading.Lock()

    def one(i: int) -> None:
        t0 = time.time()
        r = call(a.port, b, req["params"].get("betas", []))
        tool, text = contribution(r)
        row = {"i": i, "seconds": round(time.time() - t0, 1), "usage": r.get("usage"), "stop_reason": r.get("stop_reason"),
               "content": r.get("content"), "tool": tool, "contribution": text}
        with lock, f.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        u = r.get("usage") or {}
        n_in = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
        print(f"  {a.run} #{i}: {row['seconds']}s, in {n_in:,}, out {u.get('output_tokens')}, write {tool}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, range(have, a.n)))


if __name__ == "__main__":
    main()
