"""Rebuild the exact Messages API requests a subject run sent, from Claude Code's own session log (2.1.304 writes
api-request-shape: system + tools, api-request-blob: each message once by hash, api-request: base request + keep +
tail hashes), and cut out the turn where a phrase first appears in the subject's output.

    python3 rebuild.py RUN "phrase" [--out DIR]

Writes DIR/request.json (the request that produced the phrase: system, tools, messages, params) and
DIR/response.json (the assistant message it got back: thinking, text, tool calls).
"""

import argparse
import json
from pathlib import Path

SB = Path.home() / "split-brain-run"


def load(run: str) -> list[dict]:
    files = sorted((SB / "runs" / run / "claude" / "projects").glob("*/*.jsonl"))
    assert len(files) == 1, files
    return [json.loads(l) for l in files[0].open()]


def transcript(L: list[dict]) -> list[dict]:
    """The main thread as API messages: assistant entries merged by message id, consecutive user entries (one per
    parallel tool result) merged into one message. Parallel tool calls are logged interleaved (call 1, result 1,
    call 2, result 2): a call whose message id is the assistant message before the current tool-result message
    joins that assistant message."""
    groups = []
    for x in L:
        if x.get("isSidechain") or x["type"] not in ("assistant", "user"):
            continue
        m, role = x["message"], x["type"]
        c = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        same = groups and groups[-1]["role"] == role and (role == "user" or groups[-1]["_id"] == m["id"])
        interleaved = (role == "assistant" and len(groups) >= 2 and groups[-2]["_id"] == m["id"]
                       and all(b.get("type") == "tool_result" for b in groups[-1]["content"]))
        if interleaved:
            groups[-2]["content"] += c
        elif same:
            groups[-1]["content"] += c
        else:
            groups.append({"role": role, "_id": m.get("id"), "content": list(c)})
    return groups


def ids(m: dict) -> tuple:
    return tuple(c.get("id") or c.get("tool_use_id") for c in m["content"] if c.get("type") in ("tool_use", "tool_result"))


def fill(prev: dict, groups: list[dict]) -> dict:
    """A message whose blob was not logged (28 of 99 turns in p05-c1-A0-q27b): the transcript message after `prev`,
    found by its tool ids. Checked against every logged blob: 126 of 126 match."""
    i = next(i for i, g in enumerate(groups) if ids(g) == ids(prev) and g["role"] == prev["role"])
    g = groups[i + 1]
    return {"role": g["role"], "content": g["content"]}


def requests(L: list[dict]) -> list[dict]:
    shapes = {x["shapeHash"]: x["shape"] for x in L if x["type"] == "api-request-shape"}
    blobs = {x["hash"]: x["message"] for x in L if x["type"] == "api-request-blob"}
    groups = transcript(L)
    by_id, out = {}, []
    for r in (x for x in L if x["type"] == "api-request"):
        base = by_id[r["base"]]["messages"] if r.get("base") else []
        msgs = base[: r["keep"]]
        for h in r["tail"]:
            if h in blobs:
                msgs.append(blobs[h])
            else:
                msgs.append(fill(next(m for m in reversed(msgs) if m["role"] != "system"), groups) | {"_filled": True})
        req = {"id": r["id"], "timestamp": r["timestamp"], **shapes[r["shapeHash"]], "messages": msgs, "params": r["params"]}
        by_id[r["id"]] = req
        out.append(req)
    return out


def has(x, phrase: str) -> bool:
    """phrase occurs in some string inside x (json.dumps would escape quotes and non-ASCII)."""
    if isinstance(x, str):
        return phrase in x
    if isinstance(x, dict):
        return any(has(v, phrase) for v in x.values())
    if isinstance(x, list):
        return any(has(v, phrase) for v in x)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("phrase")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    reqs = requests(load(a.run))
    hit = next(i for i, r in enumerate(reqs) if has(r["messages"], a.phrase))
    req, nxt = reqs[hit - 1], reqs[hit]
    assert not has(req["messages"], a.phrase)
    n = len(req["messages"])
    assert nxt["messages"][:n] == req["messages"], "next request does not extend this one"
    resp = nxt["messages"][n]
    assert resp["role"] == "assistant" and has(resp, a.phrase)
    out = Path(a.out or Path(__file__).parent / "out" / a.run)
    out.mkdir(parents=True, exist_ok=True)
    (out / "request.json").write_text(json.dumps(req, indent=1))
    (out / "response.json").write_text(json.dumps(resp, indent=1))
    kinds = [c["type"] for c in resp["content"]]
    hist = [c["type"] for m in req["messages"] if m["role"] == "assistant" for c in m["content"]]
    print(f"request {hit - 1} of {len(reqs)} ({req['timestamp']}): {n} messages, {len(json.dumps(req)):,} chars; "
          f"response blocks {kinds}; history blocks: {hist.count('thinking')} thinking, {hist.count('text')} text, "
          f"{hist.count('tool_use')} tool_use -> {out}")


if __name__ == "__main__":
    main()
