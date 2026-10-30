"""Re-draws of the 7 missing single-turn replies so every cell of the four-model SoRH tables is out of 20 (her "Yes,
mark as redraws", 27 Oct). Design: notes/sorh_redraws_design.md.

  .venv/bin/python src/sorh_redraws.py build           # cells files for the three first-round stages
  .venv/bin/python src/sorh_redraws.py build_round 2   # DeepSeek jobs cut again at exactly 32,768 -> redraw_ds_r2
  .venv/bin/python src/sorh_redraws.py status          # what each job has so far (numbers only)

overlay(model) gives, for each job that has a usable re-draw, the record that replaces the missing one in the page's
tables. That is the latest round's record that wasn't cut during reasoning. A re-draw cut during reasoning at our own
limit stays missing. One cut at exactly 32,768 (SiliconFlow's cap on some calls) goes to the next round, up to round 3.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sorh_deepseek20 as D  # noqa: E402

PRE = ROOT / "notes" / "sorh_prereg"
LOGS = ROOT / "logs" / "sorh_ablation"
QWEN, DS = "Qwen 3.8 2.4T", "DeepSeek V4 Pro"
# (model label, cell, prompt, first-round stage, why it was missing)
JOBS = [(QWEN, "c5_eval", "sorh_821", "redraw_q24t", "cut during reasoning at 24,000 (our limit)"),
        (QWEN, "c6_score_first", "sorh_164", "redraw_q24t", "cut during reasoning at 24,000 (our limit)"),
        (DS, "c5_eval", "sorh_219", "redraw_ds64", "cut at 32,768 (SiliconFlow's cap)"),
        (DS, "c5_eval", "sorh_702", "redraw_ds64", "cut at 32,768 (SiliconFlow's cap)"),
        (DS, "c6_score_first", "sorh_845", "redraw_ds64", "cut at 32,768 (SiliconFlow's cap)"),
        (DS, "c5_training", "sorh_931", "redraw_ds64", "no record (3 provider errors)"),
        (DS, "c5_eval", "sorh_931", "redraw_ds128", "reasoned through our full 64,000")]
STAGES = {"redraw_q24t": {"model": "qwen/qwen3.8-2.4t-a95b", "max_tokens": 64000, "judges": "--"},
          "redraw_ds64": {"model": "deepseek/deepseek-v4-pro", "max_tokens": 64000, "judges": "--no-reasoning-judge"},
          "redraw_ds128": {"model": "deepseek/deepseek-v4-pro", "max_tokens": 128000, "judges": "--no-reasoning-judge"},
          "redraw_ds_r2": {"model": "deepseek/deepseek-v4-pro", "max_tokens": None, "judges": "--no-reasoning-judge"},
          "redraw_ds_r3": {"model": "deepseek/deepseek-v4-pro", "max_tokens": None, "judges": "--no-reasoning-judge"}}
CAP_32K = 32768
COLUMN_LIMIT = {QWEN: 24000, DS: 64000}  # max_tokens of the rest of each model's column in the page's tables


def limit(model, cell, prompt):
    """max_tokens a job's re-draws ran at (rounds 2-3 keep the job's first-round limit)."""
    st = next(s for m, c, p, s, _ in JOBS if (m, c, p) == (model, cell, prompt))
    return STAGES[st]["max_tokens"]


def room_note(done):
    """The verifier's point for the page: name the re-draws that had a higher limit than the rest of their column.
    done = iterable of (model, cell, prompt) re-draws in use."""
    more = [(m, c, p) for m, c, p in sorted(done) if limit(m, c, p) > COLUMN_LIMIT[m]]
    if not more:
        return ""
    return ("These re-draws ran with a higher limit than the rest of their column, and they were the long-reasoning "
            "cases, so they had more room: " + "; ".join(
                f"{m} {c}/{p} at max_tokens {limit(m, c, p):,} (the rest {COLUMN_LIMIT[m]:,})" for m, c, p in more) + ".")


def texts():
    return {(r["cell"], r["prompt_id"]): r for r in D.jl(D.OUT)}


def write(stage, rows):
    out = PRE / f"{stage}_cells.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {out.relative_to(ROOT)}: {len(rows)} rows; sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


def build():
    t = texts()
    for st in ("redraw_q24t", "redraw_ds64", "redraw_ds128"):
        write(st, [t[(c, p)] for m, c, p, s, _ in JOBS if s == st])


def recs(stage):
    p = LOGS / stage / "records.jsonl"
    return {(r["cell"], r["prompt_id"]): r for r in D.jl(p)} if p.exists() else {}


def capped(r):
    ct = (r.get("usage") or {}).get("completion_tokens") or 0
    return r.get("finish") == "length" and not (r.get("reply") or "").strip() and ct == CAP_32K


def cut_reasoning(r):
    return r.get("finish") == "length" and not (r.get("reply") or "").strip()


def build_round(n):
    """DeepSeek jobs whose latest re-draw was cut at exactly 32,768 go to round n (2 or 3), at that job's max_tokens."""
    t, prev = texts(), (["redraw_ds64", "redraw_ds128"] if n == 2 else ["redraw_ds_r2"])
    rows, lim = [], set()
    for st in prev:
        for k, r in recs(st).items():
            if capped(r):
                rows.append(t[k])
                lim.add(STAGES[st]["max_tokens"] or 64000)
    assert len(lim) <= 1, f"mixed max_tokens in round {n}: {lim}; run them as separate stages"
    write(f"redraw_ds_r{n}", rows)
    print(f"round {n}: {len(rows)} jobs at max_tokens {lim.pop() if lim else '-'}")


def overlay(model):
    """(cell, prompt) -> the usable re-draw record for that model (latest round not cut during reasoning)."""
    order = ["redraw_q24t"] if model == QWEN else ["redraw_ds64", "redraw_ds128", "redraw_ds_r2", "redraw_ds_r3"]
    out = {}
    for st in order:
        for k, r in recs(st).items():
            if not cut_reasoning(r):
                out[k] = r
            elif k in out:
                pass
    return {k: r for k, r in out.items() if (model, k[0], k[1]) in {(m, c, p) for m, c, p, _, _ in JOBS}}


def status():
    for m, c, p, st, why in JOBS:
        rows = [(s, recs(s).get((c, p))) for s in STAGES if recs(s).get((c, p))]
        print(f"{m} {c}/{p} ({why}): " + ("; ".join(
            f"{s}: finish {r['finish']}, completion {(r.get('usage') or {}).get('completion_tokens')}"
            for s, r in rows) or "not drawn") + f" | usable: {'yes' if (c, p) in overlay(m) else 'no'}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "build_round":
        build_round(int(sys.argv[2]))
    else:
        status()
