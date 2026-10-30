"""Export the debrief probes (pilots/debrief.md) for the dashboard page /debrief: one summary file with every sample's
codes (hand codes from debrief_hand/, regex columns from debrief_code.rows(), the plan probe's deliberate / slip
reading from debrief_attrib), the runs (kind, model, the file as written, the in-run plan quote, the swap edits) and
the probe wordings; one detail file per run with every sample's reply (thinking, text, tool calls with the stub each
got) plus the run's real write reply (thinking included) and the request's last user turn; and one history file per
run with every reply before the write (the reasoning the probes branch from).

    python3 debrief_view.py      # -> ~/split-brain-run/debrief/view/{summary.json, <run>.json, <run>.history.json}
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import debrief as db  # noqa: E402
import debrief_attrib as da  # noqa: E402
import debrief_code as dc  # noqa: E402
import rebuild  # noqa: E402

OUT = dc.D / "view"
POST = ["source", "honest", "other", "plan", "quote", "why", "judge_q", "judge_flag", "task", "fix", "fix_src", "reader"]
PRE = ["pre0", "pre_cost", "pre_known", "pre", "pre_user", "pre_free", "pre_name", "pre_draft"]
STUB = {"edit": "The file submission/contribution.md has been updated successfully.", "read": "(the file as written)",
        None: "Tool not available during this check."}


def content(blocks: list[dict]) -> list[dict]:
    out = []
    for c in blocks or []:
        t = c.get("type")
        if t == "thinking":
            out.append({"type": "thinking", "text": c.get("thinking") or ""})
        elif t == "text":
            out.append({"type": "text", "text": c.get("text") or ""})
        elif t == "tool_use":
            out.append({"type": "tool", "name": c.get("name"), "input": c.get("input"), "kind": db.touches(c),
                        "stub": STUB[db.touches(c)]})
    return out


def real_write(run: str, swaps: list | None = None) -> dict | None:
    """the run's own write reply (thinking, text, the tool call) and the last user turn before it; for a swap run, the
    write as the model saw it (the credit deleted, as debrief.py --swap does)"""
    base = run.split("@")[0]
    try:
        reqs = rebuild.requests(rebuild.load(base))
    except Exception as e:  # noqa: BLE001
        print(f"  {run}: no rebuild ({e})")
        return None
    ws = db.writes(reqs)
    k, resp, _tool, _text = ws[db.WRITE.get(base, 0)]
    resp = json.loads(json.dumps(resp))
    for old, new in swaps or []:
        for c in resp["content"]:
            if c.get("type") == "tool_use":
                for key in ("content", "command"):
                    v = (c.get("input") or {}).get(key)
                    if isinstance(v, str) and old in v:
                        c["input"][key] = v.replace(old, new)
    last = reqs[k]["messages"][-1]
    parts = last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
    user = []
    for c in parts:
        if c.get("type") == "text":
            user.append({"type": "text", "text": c["text"]})
        elif c.get("type") == "tool_result":
            v = c.get("content")
            v = v if isinstance(v, str) else "\n".join(x.get("text", "") for x in v or [] if isinstance(x, dict))
            user.append({"type": "tool_result", "text": v[:4000] + (" …" if len(v) > 4000 else "")})
    return {"reply": content(resp["content"]), "user": user, "request": k}


def history(run: str) -> list[dict]:
    """every assistant reply before the write (thinking, text, tool calls) with the tool results it got, in order"""
    base = run.split("@")[0]
    reqs = rebuild.requests(rebuild.load(base))
    k = db.writes(reqs)[db.WRITE.get(base, 0)][0]
    out = []
    for m in reqs[k]["messages"]:
        parts = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
        if m["role"] == "assistant":
            out.append({"reply": len(out), "content": content(parts), "results": []})
        elif out:
            for c in parts:
                if c.get("type") == "tool_result":
                    v = c.get("content")
                    v = v if isinstance(v, str) else "\n".join(x.get("text", "") for x in v or [] if isinstance(x, dict))
                    out[-1]["results"].append(v[:1500] + (f" … [{len(v) - 1500:,} more chars]" if len(v) > 1500 else ""))
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rows = list(dc.rows())
    swaps = json.loads((HERE / "debrief_swaps.json").read_text())
    runs = []
    for run in sorted({r["run"] for r in rows}, key=lambda r: (["lost", "decided", "credited", "swap"].index(dc.KIND[r]), r)):
        d = dc.D / run
        w = json.loads((d / "write.json").read_text())
        base = run.split("@")[0]
        runs.append({"run": run, "base": base, "kind": dc.KIND[run], "model": dc.model(run), "contribution": w["contribution"],
                     "timestamp": w["timestamp"], "quote": db.QUOTE.get(base) or (db.WHY.get(base) if run.endswith("@swap") else None),
                     "why": db.WHY.get(base),
                     "swap": [{"removed": a, "kept": b} for a, b in swaps.get(base, [])] if run.endswith("@swap") else None})
        detail = {"run": run, "write": real_write(run, swaps.get(base) if run.endswith("@swap") else None), "samples": {}}
        for f in sorted(d.glob("*.jsonl")):
            for l in f.open():
                r = json.loads(l)
                detail["samples"].setdefault(r["probe"], []).append({
                    "i": r["i"], "question": r["question"], "edit": r.get("edit"),
                    "turns": [{"content": content(t.get("content")), "seconds": t.get("seconds"), "error": t.get("error")}
                              for t in r["turns"]]})
        for v in detail["samples"].values():
            v.sort(key=lambda s: s["i"])
        (OUT / f"{run}.json").write_text(json.dumps(detail))
        (OUT / f"{run}.history.json").write_text(json.dumps({"run": run, "replies": history(run)}))
    # the plan attribution, keyed like the rows
    attrib = {}
    for run in {r["run"] for r in rows}:
        f = dc.D / run / "plan.jsonl"
        if f.exists():
            for l in f.open():
                r = json.loads(l)
                attrib[(run, r["i"])] = da.classify(dc.blocks(r, "text"))
    keep = ["run", "probe", "i", "edited", "edit_names", "edit_credits", "answer_names", "think_chars", "think_score",
            "verdict", "belief", "think", "reason", "action", "note", "opening"]
    S = [{**{k: r[k] for k in keep}, "attrib": attrib.get((r["run"], r["i"]), "") if r["probe"] == "plan" else ""} for r in rows]
    template = {"quote": db.QUOTE_Q, "why": db.WHY_Q}
    probes = [{"id": p, "family": "post", "question": db.PROBES.get(p, template.get(p, ""))} for p in POST] + \
             [{"id": p, "family": "pre", "question": db.PRE[p]} for p in PRE]
    (OUT / "summary.json").write_text(json.dumps({"runs": runs, "probes": probes, "samples": S}))
    print(f"{len(runs)} runs, {len(S)} samples -> {OUT}")


if __name__ == "__main__":
    main()
