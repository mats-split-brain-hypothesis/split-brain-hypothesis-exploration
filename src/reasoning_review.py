"""Local, read-only evidence packets and an exact record of inspected text ranges.

No model calls. Source records are never changed. The inspection ledger records
what was printed, not a claim that every source token was manually reviewed.
"""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs/reasoning_review/2026-10-27"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@lru_cache(maxsize=32)
def jsonlines(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def text_parts(content):
    if isinstance(content, str):
        return content, ""
    return ("\n".join(c.text for c in content if c.type == "text"),
            "\n".join(c.reasoning for c in content if c.type == "reasoning"))


def from_eval(src):
    from inspect_ai.log import read_eval_log_sample
    s = read_eval_log_sample(src.get("path") or src["log_path"], src["sample_id"],
                             int(src.get("epoch") or 1), resolve_attachments=True)
    events = []
    for e in s.events or []:
        if type(e).__name__ == "ModelEvent" and getattr(e, "output", None) and e.output.choices:
            m = e.output.choices[0].message
            vis, rea = text_parts(m.content)
            sig = (vis, [(t.function, t.arguments) for t in m.tool_calls or []])
            events.append((sig, rea))
    messages = []
    for i, m in enumerate(s.messages):
        vis, rea = text_parts(m.content)
        calls = [(t.function, t.arguments) for t in getattr(m, "tool_calls", None) or []]
        origin = "message"
        if m.role == "assistant" and not rea:
            for j, (sig, candidate) in enumerate(events):
                if sig == (vis, calls) and candidate:
                    rea = candidate
                    events.pop(j)
                    origin = "matching_model_event"
                    break
        messages.append(dict(index=i, role=m.role, text=vis, reasoning=rea,
                             reasoning_origin=origin, tool_calls=calls,
                             error=str(getattr(m, "error", "") or "")))
    return dict(messages=messages, error=str(s.error or ""), source=src)


def packet(row):
    src = row.get("source")
    if not src and row.get("rounds"):
        src = dict(kind="rounds", rounds=[r.get("source", r) for r in row["rounds"]])
    if isinstance(src, list):
        src = dict(kind="turns", turns=src)
    if not src:
        return dict(row=row, missing=True, messages=[])
    kind = src.get("kind")
    if kind in ("jsonl", "json"):
        r = (jsonlines(src["path"])[int(src["line"]) - 1] if kind == "jsonl"
             else json.loads(Path(src["path"]).read_text()))
        messages = [dict(index=0, role="user", text=r.get("prompt", ""), reasoning=""),
                    dict(index=1, role="assistant", text=r.get("reply") or "",
                         reasoning=r.get("reasoning") or "")]
        result = dict(messages=messages, source=src,
                      metadata={k:v for k,v in r.items() if k not in ("prompt", "reply", "reasoning", "messages")})
    elif kind == "eval":
        result = from_eval(src)
    elif kind == "turns":
        messages = []
        for t in sorted(src["turns"], key=lambda t:t["turn"]):
            r = jsonlines(t["path"])[int(t["line"]) - 1]
            messages.extend([dict(index=len(messages), turn=t["turn"], role="user", text=r.get("prompt", ""), reasoning=""),
                             dict(index=len(messages)+1, turn=t["turn"], role="assistant", text=r.get("reply") or "", reasoning=r.get("reasoning") or "")])
        result = dict(messages=messages, source=src)
    elif kind == "rounds":
        messages = []
        for rd in src["rounds"]:
            rr = from_eval(rd.get("source", rd))
            for msg in rr["messages"]:
                msg = dict(msg, round=rd.get("round"), local_index=msg["index"], index=len(messages))
                messages.append(msg)
        result = dict(messages=messages, source=src)
    else:
        raise ValueError(src)
    return dict(row=row, **result)


def get(rid):
    dest = OUT / "packets" / (rid + ".json")
    if dest.exists():
        return json.loads(dest.read_text())
    rows = json.loads((OUT / "inventory.json").read_text())["rows"]
    row = next(r for r in rows if r["review_id"] == rid)
    result = packet(row)
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+")
    parser.add_argument("--overview", action="store_true")
    parser.add_argument("--message", type=int)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--field", choices=("reasoning", "text"), default="reasoning")
    args = parser.parse_args()
    for rid in args.ids:
        p = get(rid)
        r = p["row"]
        print("\nRECORD", rid, r.get("model"), r.get("version"), r.get("task") or r.get("unit"), r.get("labels"))
        for m in p["messages"]:
            if args.overview:
                print("MESSAGE", m["index"], m["role"], "reasoning_chars", len(m["reasoning"]),
                      "text_chars", len(m["text"]), "tools", [c[0] for c in m.get("tool_calls", [])],
                      "cue", m["text"][:180] if m["role"] == "user" else "")
                continue
            if args.message is not None and m["index"] != args.message:
                continue
            if m["role"] != "assistant" and args.field == "reasoning":
                print("CONTEXT", m["index"], m["role"], m["text"][:1800])
                continue
            text = m.get(args.field, "")
            start = max(0, len(text)+args.start) if args.start < 0 else min(args.start,len(text))
            end = min(args.end, len(text)) if args.end is not None else len(text)
            if end < 0: end = max(0,len(text)+end)
            if end < start: raise ValueError("End precedes start")
            print("MESSAGE", m["index"], m["role"], args.field, f"chars[{start}:{end}]/{len(text)}")
            print(text[start:end])
            if args.field == "reasoning":
                print("VISIBLE RESULT", m["text"][:1100], "TOOLS", str(m.get("tool_calls", []))[:1800])
            entry = dict(id=rid, message=m["index"], field=args.field, start=start, end=end,
                         total_chars=len(text), sha256=sha(text))
            with (OUT / "inspection_ranges.jsonl").open("a") as f:
                f.write(json.dumps(entry)+"\n")


if __name__ == "__main__":
    main()
