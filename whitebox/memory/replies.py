"""A run's replies as the model produced them: one entry per API reply (assistant entries merged by message id),
with its thinking, visible text and tool calls, and the tool results that followed. From Claude Code's session log."""

import json
from pathlib import Path

SB = Path.home() / "split-brain-run"


def replies(run: str) -> list[dict]:
    files = sorted((SB / "runs" / run / "claude" / "projects").glob("*/*.jsonl"))
    out, ids = [], {}
    for line in files[0].open():
        x = json.loads(line)
        if x.get("isSidechain"):
            continue
        if x.get("type") == "assistant":
            m = x["message"]
            if m["id"] not in ids:
                ids[m["id"]] = len(out)
                out.append({"i": len(out), "t": x["timestamp"][11:19], "thinking": "", "text": "", "calls": [], "results": []})
            r = out[ids[m["id"]]]
            for c in m["content"]:
                if c["type"] == "thinking":
                    r["thinking"] += c["thinking"]
                elif c["type"] == "text":
                    r["text"] += c["text"]
                elif c["type"] == "tool_use":
                    r["calls"].append(json.dumps(c["input"]))
        elif x.get("type") == "user" and out and isinstance(x["message"]["content"], list):
            for c in x["message"]["content"]:
                if c.get("type") == "tool_result":
                    cc = c.get("content")
                    out[-1]["results"].append(cc if isinstance(cc, str) else json.dumps(cc))
    return out


def visible_before(rs: list[dict], i: int) -> str:
    """Everything the model could see at reply i: earlier visible text, tool calls and results (not thinking)."""
    return "\n".join(r["text"] + "\n" + "\n".join(r["calls"]) + "\n" + "\n".join(r["results"]) for r in rs[:i])
