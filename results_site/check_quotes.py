"""Check every quote in results_site/quotes_sorh_ib.json against its record, by code.

  .venv/bin/python results_site/check_quotes.py

For each row: read the named record (a .jsonl line, an Inspect .eval message, or a committed notes file), take the
named field, collapse whitespace on both sides, and require each '…'-separated piece of the quote to appear in order.
Also checks the record's cell / prompt / sample / task labels where the record carries them. Exits non-zero on any
failure. Paths are relative to the repository root (logs/ is not in git; run from a checkout that has it).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_evals = {}


def norm(s):
    return " ".join((s or "").split())


def eval_fields(path, sample_id, epoch, idx):
    from inspect_ai.log import read_eval_log
    if path not in _evals:
        _evals[path] = read_eval_log(str(ROOT / path))
    s = next(x for x in _evals[path].samples if str(x.id) == sample_id and x.epoch == epoch)
    m = s.messages[idx]
    out = {}
    if isinstance(m.content, str):
        out["text"] = m.content
    else:
        out["reasoning"] = "".join(getattr(c, "reasoning", "") or "" for c in m.content if getattr(c, "type", "") == "reasoning")
        out["text"] = "".join(getattr(c, "text", "") or "" for c in m.content if getattr(c, "type", "") == "text")
    for tc in getattr(m, "tool_calls", None) or []:
        for k, v in (tc.arguments or {}).items():
            if isinstance(v, str):
                out[f"tool:{tc.function}.{k}"] = v
    return out, m.role


def main():
    doc = json.load(open(ROOT / "results_site/quotes_sorh_ib.json"))
    fails = 0
    for r in doc["rows"]:
        src = r["source"]
        try:
            if src["kind"] == "jsonl":
                with open(ROOT / src["path"], encoding="utf-8") as f:
                    rec = json.loads(next(l for i, l in enumerate(f, 1) if i == src["line"]))
                hay = rec[{"reply": "reply", "reasoning": "reasoning", "user message": "prompt"}[r["field"]]]
                for k, want in (("cell", r.get("cell")), ("prompt_id", r.get("prompt"))):
                    if want and k in rec and rec.get("arm") is None and rec[k] != want:
                        raise AssertionError(f"record {k} {rec[k]!r} != {want!r}")
            elif src["kind"] == "eval":
                fields, role = eval_fields(src["path"], src["sample_id"], src["epoch"], src["message_index"])
                if role != src.get("role", role):
                    raise AssertionError(f"role {role} != {src['role']}")
                hay = fields[r["field"]]
            elif src["kind"] == "notes":
                hay = subprocess.run(["git", "-C", str(ROOT), "show", f"{src['commit']}:{src['path']}"], check=True,
                                     capture_output=True, text=True).stdout
            else:
                raise AssertionError(f"unknown source kind {src['kind']}")
            h, pos = norm(hay), 0
            for seg in [norm(x) for x in r["quote"].split("…") if x.strip()]:
                k = h.find(seg, pos)
                if k < 0:
                    raise AssertionError(f"not found: {seg[:70]!r}")
                pos = k + len(seg)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print("FAIL", r["id"], e)
    print(f"{len(doc['rows'])} quotes checked;", "OK" if not fails else f"{fails} failures")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
