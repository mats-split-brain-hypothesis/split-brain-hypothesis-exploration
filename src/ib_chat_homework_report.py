"""Her homework wording vs the earlier automated-framing chat replies, per model and task (pre-registration:
notes/ib_chat_vs_harness.md, "Amendment 4"). No API calls; reads visible text only (CONTRA), never reasoning.

    .venv/bin/python src/ib_chat_homework_report.py [logs/ib_chat_homework]

Homework replies: logs/ib_chat_homework/<setup>/ (one reply per task). Automated chat replies: each setup's earlier chat
dir. Writes <root>/report.json and prints a markdown table. A look (1 reply per task per model), no reading rule.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ib_chat_vs_harness_report as R  # noqa: E402
from ib_chat_vs_harness import RUN4_TASKS  # noqa: E402

MODELS = [("qwen", "Qwen 3.8 2.4T (SiliconFlow)", "logs/ib_chat_vs_harness/chat"),
          # her re-run (27 Oct): homework and automated chat both on novita/fp8 at max_tokens 393,216
          ("ds", "DeepSeek V4 Pro (Novita, max_tokens 393,216)", "logs/ib_chat_vs_harness_dsn/chat"),
          ("glm", "GLM 5.2 (SiliconFlow)", "logs/ib_chat_vs_harness_glm/chat"),
          ("q27p", "Qwen 3.8 27B (Parasail)", "logs/ib_chat_vs_harness_q27p/chat")]
TASKS = RUN4_TASKS.split(",")
# ImpossibleBench's find_code: the last match of P1 + P2 (P1 matches listed first), else the whole reply.
P1 = re.compile(r"```python\n(.*?)```", re.DOTALL)
P2 = re.compile(r"```\n(.*?)```", re.DOTALL)
FENCED = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)   # real fenced blocks, any language tag, in order


def blocks(text, entry_point):
    """Code-block facts for one visible reply (the verifier's point at 26b58c7): how many fenced blocks, which text
    find_code scores, whether that text is one of the real blocks and holds `def <entry_point>(`, and whether another
    block holds it. P2 can also match the stretch between two blocks (from a closing fence to the next opening one)."""
    real = FENCED.findall(text)
    m = P1.findall(text) + P2.findall(text)
    scored = m[-1] if m else text
    d = f"def {entry_point}("
    return dict(fenced_blocks=len(real), find_code_matches=len(m),
                scored="whole reply (no block)" if not m else ("a real block" if scored in real else "text between blocks"),
                scored_has_function=d in scored,
                other_block_has_function=any(d in b for b in real if b != scored))


def raw_finish(e):
    """The provider's raw finish_reason for one model event (metadata only)."""
    raw = (e.call.response if e is not None and e.call else None) or {}
    ch = (raw.get("choices") or [{}])[0] if isinstance(raw, dict) else {}
    return ch.get("finish_reason")


def missing_cause(end, finish, out_t, max_t):
    """Why a reply is missing (the verifier's point after ff1b3ef):
    - raw finish "error": a provider error (an empty reply);
    - a length stop below 90% of the max_tokens sent: the provider's own ceiling (e.g. SiliconFlow's 32,768);
    - a length stop at or near it: our limit;
    - a length stop with no max_tokens sent: the provider's limit."""
    if finish == "error":
        return f"provider error (raw finish 'error', {out_t} tokens)"
    if end in R.CUT or finish == "length":
        if max_t is None:
            return f"provider limit ({out_t} tokens, no max_tokens sent)"
        if out_t is not None and out_t < 0.9 * max_t:
            return f"provider cut ({out_t} of {max_t} requested)"
        return f"at our limit ({out_t} of {max_t} requested)"
    return f"empty reply (raw finish {finish!r})"


def block_rows(d):
    """{task|rep: blocks(...) + token facts} for the replies in a log dir (visible text only). A reply cut below the
    max_tokens it requested is a provider cut (e.g. SiliconFlow's 32,768 per-call ceiling), not ours."""
    out = {}
    for s in R.samples_in(d):
        if s.error or not s.scores:
            continue
        text = R.final_text(s, "chat")
        b = blocks(text, s.metadata["entry_point"])
        ev = [e for e in s.events if e.event == "model"]
        e = ev[-1] if ev else None
        out_t = e.output.usage.output_tokens if e and e.output and e.output.usage else None
        max_t = e.config.max_tokens if e and e.config else None
        end = s.output.stop_reason if s.output else None
        fin = raw_finish(e)
        missing = end in R.CUT or not text.strip()
        # below 90% of the request = the provider's own ceiling; at or near it = our limit (counts differ slightly)
        b.update(output_tokens=out_t, max_tokens_requested=max_t, raw_finish=fin,
                 missing_cause=missing_cause(end, fin, out_t, max_t) if missing else None,
                 provider_cut=bool(end in R.CUT and out_t is not None and max_t is not None and out_t < 0.9 * max_t))
        out[str(s.id).split("|")[1] + "|" + str(s.id).split("|")[2]] = b
    return out


def outcome(r):
    if r is None:
        return "not run"
    if r["error"]:
        return "error"
    if r["missing"]:
        return f"missing ({r['end']})"
    return "hack" if r["hack"] else "no hack"


def homework_rows(root, setup):
    """{task: row} from <root>/<setup>, with re-drawn replies in <root>/<setup>_redraw replacing those ids (her OK'd
    re-draws of empty provider-error / cut replies, 27 Oct). A replaced row gets redrawn=True and the original outcome."""
    rows = {r["task"]: r for r in R.chat_rows(Path(root) / setup)} if (Path(root) / setup).exists() else {}
    rd = Path(root) / f"{setup}_redraw"
    for r in (R.chat_rows(rd) if rd.exists() else []):
        old = rows.get(r["task"])
        # both draws were paid for: the replaced draw's cost is kept and counted in the totals
        rows[r["task"]] = dict(r, redrawn=True, original=outcome(old), cost=r["cost"] + ((old or {}).get("cost") or 0.0))
    return rows


def homework_blocks(root, setup):
    b = block_rows(Path(root) / setup) if (Path(root) / setup).exists() else {}
    rd = Path(root) / f"{setup}_redraw"
    b.update(block_rows(rd) if rd.exists() else {})
    return b


def summarize(root):
    out = {}
    for setup, name, chat_dir in MODELS:
        hw = homework_rows(root, setup)
        hb = homework_blocks(root, setup)
        auto = R.chat_rows(chat_dir)
        hw_ok = [r for r in hw.values() if not r["error"] and not r["missing"]]
        au_ok = [r for r in auto if not r["error"] and not r["missing"]]
        per = {}
        for t in TASKS:
            h = hw.get(t)
            a = [r for r in au_ok if r["task"] == t]
            per[t] = dict(homework=outcome(h) + (f" (re-drawn; first draw {h['original']})" if h and h.get("redrawn") else ""),
                          homework_blocks=hb.get(f"{t}|r1"), homework_scaffold=(h or {}).get("scaffold_rule"),
                          homework_names_contradiction=(h or {}).get("points_out"),
                          automated=f"{sum(r['hack'] for r in a)}/{len(a)}",
                          automated_missing=sum(1 for r in auto if r["task"] == t and (r["error"] or r["missing"])))
        out[setup] = dict(model=name, per_task=per,
                          homework=dict(hack=R.kn(hw_ok), scaffold_rule=f"{sum(r['scaffold_rule'] for r in hw_ok)}/{len(hw_ok)}",
                                        names_contradiction=f"{sum(r['points_out'] for r in hw_ok)}/{len(hw_ok)}",
                                        no_code=sum(not r["code_found"] for r in hw_ok),
                                        missing=[dict(id=r["id"], end=r["end"]) for r in hw.values() if r.get("missing")],
                                        errors=[r["id"] for r in hw.values() if r["error"]],
                                        cost=round(sum(r["cost"] for r in hw.values()), 3)),
                          automated=dict(hack=R.kn(au_ok), names_contradiction=f"{sum(r['points_out'] for r in au_ok)}/{len(au_ok)}",
                                         # on the tasks with a usable homework reply only (the verifier's point: missing
                                         # replies cluster on some tasks, so the full counts compare different task sets)
                                         hack_matched_tasks=R.kn([r for r in au_ok if r["task"] in {h["task"] for h in hw_ok}]),
                                         matched_tasks=sorted({h["task"] for h in hw_ok})))
    return out


def table(out):
    lines = ["| Model | " + " | ".join(TASKS) + " | Homework hacked | Automated chat hacked |",
             "|---|" + "---|" * (len(TASKS) + 2)]
    def cell(p):
        b = p["homework_blocks"]
        flag = ""
        if b and p["homework"].startswith("missing"):
            flag = f"; {b['missing_cause']}"
        elif b and (b["fenced_blocks"] > 1 or b["scored"] != "a real block" or not b["scored_has_function"]):
            flag = (f"; {b['fenced_blocks']} blocks, scored {b['scored']}, def in scored: {b['scored_has_function']}, "
                    f"def in another: {b['other_block_has_function']}")
        return f"{p['homework']}{flag} (auto {p['automated']})"
    for setup, v in out.items():
        cells = [cell(v["per_task"][t]) for t in TASKS]
        lines.append(f"| {v['model']} | " + " | ".join(cells) + f" | {v['homework']['hack']} | {v['automated']['hack']} |")
    return "\n".join(lines)


def selftest():
    def row(t, hack, missing=False, error=False):
        return dict(id=f"hw|{t}|r1", task=t, error=error, missing=missing, end="max_tokens" if missing else "stop",
                    hack=hack, scaffold_rule=hack, points_out=False, code_found=True, cost=0.1)
    assert outcome(None) == "not run" and outcome(row("t", True)) == "hack" and outcome(row("t", False)) == "no hack"
    assert outcome(row("t", False, missing=True)) == "missing (max_tokens)" and outcome(row("t", False, error=True)) == "error"
    f = "def f(x):\n    return 1\n"
    one = blocks(f"Here:\n```python\n{f}```\n", "f")
    assert one == dict(fenced_blocks=1, find_code_matches=1, scored="a real block", scored_has_function=True,
                       other_block_has_function=False), one
    # GLM 99 r2's shape: an untagged formula block, then the ```python function: find_code scores the formula
    two = blocks(f"Formula:\n```\na = b\n```\nCode:\n```python\n{f}```", "f")
    assert two["fenced_blocks"] == 2 and not two["scored_has_function"] and two["other_block_has_function"], two
    # an example block after the function
    ex = blocks(f"```python\n{f}```\nExample:\n```python\nprint(f(1))\n```", "f")
    assert ex["fenced_blocks"] == 2 and not ex["scored_has_function"] and ex["other_block_has_function"], ex
    assert blocks("def f(x):\n    return 1", "f")["scored"] == "whole reply (no block)"
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    root = sys.argv[1] if len(sys.argv) > 1 else "logs/ib_chat_homework"
    out = summarize(root)
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "report.json").write_text(json.dumps(out, indent=1))
    print(table(out))
    print(json.dumps({k: dict(homework=v["homework"], automated=v["automated"]) for k, v in out.items()}, indent=1))
