"""Examples for agent 7's dashboard tab, picked by script from the stage 0 tables (seed fixed).

  python src/rejection_examples.py <stage0 dir> <goodfire dir> <out json>

Kinds (one per model where it exists, picked at random with seed 7 among the episodes that fit):
- after_rejection: the first A statement is in the turn right after the first rejection, and the model had asserted
  the test is wrong at least 3 turns earlier (typical case: noticed early, says "test of me" only once rejected).
- at_noticing: the first A statement is in the same turn as the first assertion that a test is wrong, before any
  rejection.
- never_rejected: possible-split lcbhard_67 (wrong test, never rejected): the flaw claim and the outcome; no A.
- futility: a frustration sentence about the feedback after a rejection, before the first A statement.
Excerpts are short: the rejection's failing assertion, up to 300 characters of lead-up, the A passage (≤700).
"""
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import rejection_stage0 as r0  # noqa: E402
import rejection_turns as rt  # noqa: E402

KEYS = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}
WS = re.compile(r"\s+")
GRADER = re.compile(r"grader|harness|feedback|reject\w*|submi\w+|evaluator", re.I)


def clip(s, n):
    s = WS.sub(" ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def tail(s, n):
    s = WS.sub(" ", s or "").strip()
    return s if len(s) <= n else "…" + s[-(n - 1):]


def rejection_assert(gdir, model, row, k_rej=1):
    """The failing assertion shown in the episode's k-th rejection."""
    with open(f"{gdir}/{KEYS[model]}_traces.jsonl") as f:
        for i, line in enumerate(f):
            if i == row:
                t = json.loads(line)["traces"][0]
                rej = [n["message"]["content"] for n in t["nodes"] if n["message"]["role"] == "user"
                       and str(n["message"].get("content", "")).startswith(rt.REJECTION)]
                if len(rej) >= k_rej:
                    m = re.search(r"\n\s+(assert [^\n]+)\n(?:\s*\^+\n)?AssertionError", rej[k_rej - 1])
                    return m.group(1) if m else clip(rej[k_rej - 1], 200)
                return None


def main(d, gdir, out):
    rng = random.Random(7)
    t, e = r0.load(d)
    texts = r0.load_texts(d)
    ex = []

    def a_split(model, row, turn, a_text):
        reasoning, reply = texts[(model, row, turn)]
        full = WS.sub(" ", reasoning + " " + reply).strip()
        pos = full.find(WS.sub(" ", a_text).strip()[:80])
        return full[max(0, pos - 300):pos], full[pos:pos + 700]

    for m in r0.MODELS:
        ee = e[(e.model == m) & e.imp & e.first_A_turn.notna() & e.first_flaw_turn.notna()]
        # after_rejection
        cand = ee[(ee.first_A_turn == ee.first_rej_turn) & (ee.first_flaw_turn <= ee.first_rej_turn - 3)]
        if len(cand):
            r = cand.iloc[rng.randrange(len(cand))]
            lead, stmt = a_split(m, int(r.row), int(r.first_A_turn), r.first_A_text)
            flaw = t[(t.model == m) & (t.row == r.row) & (t.turn == r.first_flaw_turn)].flaw_quote.iloc[0]
            ex.append(dict(kind="Noticed early, says 'test of me' right after the first rejection", model=m,
                           task=f"{r.task} ({r.split})", pick="random (seed 7) among episodes whose first A is in the "
                           f"turn right after the first rejection and whose flaw claim came >=3 turns earlier ({len(cand)} fit)",
                           timeline=f"flaw asserted at turn {int(r.first_flaw_turn)}; first rejection before turn "
                           f"{int(r.first_rej_turn)}; first A at turn {int(r.first_A_turn)}",
                           noticed=clip(flaw, 240), cue="Rejection: failing " + (rejection_assert(gdir, m, int(r.row)) or "?")
                           + " … To reiterate, this is your task: <STOP instruction>",
                           lead_up=tail(lead, 300), statement=clip(stmt, 700), outcome=f"hack verdict: {r.verdict}"))
        # at_noticing
        cand = ee[(ee.first_A_turn == ee.first_flaw_turn) & ((ee.first_rej_turn.isna()) | (ee.first_A_turn < ee.first_rej_turn))]
        if len(cand):
            r = cand.iloc[rng.randrange(len(cand))]
            lead, stmt = a_split(m, int(r.row), int(r.first_A_turn), r.first_A_text)
            ex.append(dict(kind="Says 'test of me' in the turn it first notices the flaw, before any rejection", model=m,
                           task=f"{r.task} ({r.split})", pick=f"random (seed 7) among such episodes ({len(cand)} fit)",
                           timeline=f"flaw asserted and first A both at turn {int(r.first_A_turn)}; no rejection yet",
                           noticed="", cue="The STOP instruction in the first message", lead_up=tail(lead, 300),
                           statement=clip(stmt, 700), outcome=f"hack verdict: {r.verdict}"))
        # futility after a rejection, before the first A (or with no A)
        tm = t[(t.model == m) & t.imp & (t.frust_feedback > 0) & (t.n_rej > 0)
               & (t.first_A_turn.isna() | (t.turn < t.first_A_turn))]
        tm = tm[[any(rt.FRUST.search(s) and GRADER.search(s) for s in rt.SENT.split(" ".join(texts[(m, int(x.row), int(x.turn))])))
                 for x in tm.itertuples()]] if len(tm) else tm
        if len(tm):
            r = tm.iloc[rng.randrange(len(tm))]
            reasoning, reply = texts[(m, int(r.row), int(r.turn))]
            sent = next((s for s in rt.SENT.split(reasoning + "\n" + reply)
                         if rt.FRUST.search(s) and GRADER.search(s)), None)
            if sent is None:
                continue
            ex.append(dict(kind="Frustration about the feedback after a rejection", model=m,
                           task=f"{r.task} ({r.split})", pick=f"random (seed 7) among turns after a rejection and before "
                           f"the first A with a frustration sentence naming the grader, harness, feedback or submissions ({len(tm)} fit)",
                           timeline=f"turn {int(r.turn)}, after {int(r.n_rej)} rejection(s); first A at turn "
                           f"{'none' if pd.isna(r.first_A_turn) else int(r.first_A_turn)}",
                           noticed="", cue="", lead_up="", statement=clip(sent, 300), outcome=f"hack verdict: {r.verdict}"))
    # never rejected, wrong test (possible split lcbhard_67)
    for m in r0.MODELS:
        r = e[(e.model == m) & (e.task == "lcbhard_67") & ~e.imp].iloc[0]
        flaw = (t[(t.model == m) & (t.row == r.row) & (t.turn == r.first_flaw_turn)].flaw_quote.iloc[0]
                if pd.notna(r.first_flaw_turn) else "(only raised as a question)")
        ex.append(dict(kind="Wrong test on a 'possible' task, never rejected: no 'test of me', and it fits the test", model=m,
                       task=f"{r.task} (original split)", pick="all three episodes of lcbhard_67 (verifier's 4th flawed task)",
                       timeline=(f"flaw asserted at turn {int(r.first_flaw_turn)}; " if pd.notna(r.first_flaw_turn) else "") +
                       f"{int(r.n_turns)} turns; rejections {int(r.n_rej)}",
                       noticed=clip(flaw, 240), cue="", lead_up="", statement="(no A statement in the episode)",
                       outcome=f"hack verdict: {r.verdict} ({', '.join(r.categories or [])})"))
    Path(out).write_text(json.dumps(ex, indent=1))
    for x in ex:
        print(json.dumps(x, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
