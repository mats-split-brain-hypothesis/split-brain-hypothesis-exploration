"""Review v2 (researcher's comments on map rows 2a and 2b), local analysis only, no API calls.

  python src/rejection_review_v2.py logs/rejection/stage0 logs/rejection/review_v2

1. 2b as a reference bar on 2a's chart: in Goodfire's impossible-split transcripts, the first "test of me" (A) in the
   turn right after the model's own failing test run (no rejection yet) vs the turn right after the first rejection,
   both at turn 5+, same risk set (turns up to the first A), with a Mantel-Haenszel ratio matched on exact turn.
2. 2a without the STOP clause: our own ImpossibleBench runs with instruction "pass" vs "stop", first A per turn before
   any rejection vs after one. A per passage from agent 2's cached labels (logs/ib_cues/labels.jsonl, GPT-5.6 Luna,
   luna2 prompt) and agent 2's hand check of every episode with an A-labelled passage (logs/ib_cues/a_handcheck.json);
   episodes are read with agent 2's src/ib_variant_report.py (same turns and dedup), no new labels.
3. 2a on possible tasks: Goodfire's original (solvable) split, first A per turn before vs after a rejection, the four
   tasks with wrong tests (FLAWED_POSSIBLE) shown separately.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rejection_stage0 import FLAWED_POSSIBLE, MODELS, load, mh_ci, mh_ratio, risk  # noqa: E402

A2_SRC = Path(__file__).resolve().parents[1] / ".." / "agent-2-ib-cues" / "src"


def part1(t):
    imp = risk(t[t.imp], "first_A_turn")
    out = []
    for m in MODELS:
        d = imp[(imp.model == m) & (imp.turn >= 5)].copy()
        own = d[(d.n_rej == 0) & d.just_fail]
        rej1 = d[d.just_rej & (d.n_rej == 1)]
        anyrej = d[d.just_rej]
        sub = d[((d.n_rej == 0) & d.just_fail) | (d.just_rej & (d.n_rej == 1))].copy()
        sub["rej"] = sub.just_rej
        r, k1, n1, k0, n0 = mh_ratio(sub, sub.rej, "turn")
        lo, hi = mh_ci(sub, "rej", "turn", reps=1000)
        out.append(dict(model=m, own_fail=[int(own.event.sum()), len(own)], first_rejection=[int(rej1.event.sum()), len(rej1)],
                        any_rejection=[int(anyrej.event.sum()), len(anyrej)],
                        own_fail_turns=[int(own.turn.min()), int(own.turn.median()), int(own.turn.max())],
                        first_rej_turns=[int(rej1.turn.min()), int(rej1.turn.median()), int(rej1.turn.max())],
                        mh_first_rej_vs_own_fail=None if r != r else round(r, 1), ci=[lo and round(lo, 1), hi and round(hi, 1)],
                        matched_turns=[k1, n1, k0, n0]))
    return out


EXTRA_LABELS = Path("logs/rejection/review_v2/labels_luna2_ib_extra.jsonl")    # same labeller, our own cache
EXTRA_HAND = Path("logs/rejection/review_v2/a_handcheck_extra.json")           # same rule as agent 2's hand check
DIRS = None


def _ivr():
    sys.path.insert(0, str(A2_SRC.resolve()))
    import ib_variant_report as ivr  # agent 2's reader: same episodes, turns, labeller prompt and batching
    return ivr


def _dirs():
    dirs = sorted(str(p) for p in Path("logs/ib_cues").glob("round1*") if p.is_dir())
    return dirs + ["logs/ib_persistence/step3", "logs/automated_pass", "logs/student_pass"]


def _labels(ivr):
    labs = ivr.cached()
    if EXTRA_LABELS.exists():
        labs.update({json.loads(l)["id"]: json.loads(l) for l in EXTRA_LABELS.open()})
    return labs


def label_missing(budget):
    """Label, with agent 2's labeller (GPT-5.6 Luna, luna2 prompt, batches of 20), every passage of the in-scope runs
    that agent 2's cache lacks; written to EXTRA_LABELS so agent 2's file is untouched."""
    import asyncio
    ivr = _ivr()
    labs = _labels(ivr)
    rows = []
    for log, s in ivr.episodes(_dirs()):
        if (log.eval.task_args or {}).get("instruction") not in ("pass", "stop") or not s.scores or s.error:
            continue
        if "2.4t" not in str(log.eval.model):
            continue
        rows += [p for p in ivr.candidate_passages(log, s) if p["id"] not in labs]
    rows = list({r["id"]: r for r in rows}.values())
    print(f"{len(rows)} passages to label")
    EXTRA_LABELS.parent.mkdir(parents=True, exist_ok=True)
    ivr.LABELS = EXTRA_LABELS
    if rows:
        spent = asyncio.run(ivr._label(rows, budget))
        print(f"{spent['calls']} calls, ${spent['usd']:.3f}, {spent['failed']} failed batches")


def part2():
    ivr = _ivr()
    labs = _labels(ivr)
    extra_hand = json.loads(EXTRA_HAND.read_text()) if EXTRA_HAND.exists() else {}
    hand = {**ivr.handcheck(), **extra_hand}
    rows, cov = [], defaultdict(lambda: [0, 0])
    for log, s in ivr.episodes(_dirs()):
        args = log.eval.task_args or {}
        instr = args.get("instruction") or ("stop" if "_stop" in log.eval.task else None)
        if instr not in ("pass", "stop") or not s.scores or s.error:
            continue
        if "2.4t" not in str(log.eval.model):
            continue
        summ = ivr.summarise(log, s, labs)
        hc = hand.get(f"{log.eval.eval_id}|{s.id}")
        if hc:  # agent 2's hand check, or ours for the newly labelled runs (same rule)
            summ["A_final"], summ["A_status"] = hc["A"], "hand-checked"
            summ["first_A"] = (hc["first_turn"], hc["first_rej"]) if hc["A"] else None
        elif summ["A_final"]:
            summ["A_status"] = "labeller only"
        ps = list(ivr.candidate_passages(log, s))
        cov[instr][0] += sum(p["id"] in labs for p in ps)
        cov[instr][1] += len(ps)
        if any(p["id"] not in labs for p in ps):  # an unlabelled passage could hide an A: keep fully labelled episodes only
            cov[instr + " excluded (not fully labelled)"][0] += 1
            continue
        ts = ivr.turns(s)
        first = summ["first_A"][0] if summ["A_final"] and summ["first_A"] else None
        prev = 0
        for turn, n_rej, _ in ts:
            if first is not None and turn > first:
                break
            rows.append(dict(instr=instr, variant=summ["variant"], ep=f"{log.eval.eval_id}|{s.id}", turn=turn, n_rej=n_rej,
                             just_rej=n_rej > prev, event=int(turn == first), status=summ["A_status"],
                             attempts=args.get("attempts", 10)))
            prev = n_rej
    out = {}
    for instr in ("pass", "stop"):
        r = [x for x in rows if x["instr"] == instr]
        # Fisher-free summary; the per-turn comparison is descriptive (turns within an episode aren't independent).
        eps = {x["ep"] for x in r}
        epA = {x["ep"] for x in r if x["event"]}
        before = [x for x in r if x["n_rej"] == 0]
        after = [x for x in r if x["n_rej"] >= 1]
        right = [x for x in r if x["just_rej"]]
        firstA_rej = [x["n_rej"] for x in r if x["event"]]
        out[instr] = dict(episodes=len(eps), episodes_with_A=len(epA), labelled_passages=cov[instr],
                          excluded_not_fully_labelled=cov[instr + " excluded (not fully labelled)"][0],
                          before_any_rejection=[sum(x["event"] for x in before), len(before)],
                          after_a_rejection=[sum(x["event"] for x in after), len(after)],
                          turn_right_after_a_rejection=[sum(x["event"] for x in right), len(right)],
                          first_A_after_n_rejections=sorted(firstA_rej),
                          episodes_rejected=len({x["ep"] for x in r if x["n_rej"] >= 1}),
                          labeller_only_A=len({x["ep"] for x in r if x["event"] and x["status"] != "hand-checked"}),
                          variants=sorted({x["variant"] for x in r}))
    return out


def part3(t):
    pos = risk(t[~t.imp], "first_A_turn")
    out = {}
    for group, d0 in [("possible, tests correct", pos[~pos.task.isin(FLAWED_POSSIBLE)]),
                      ("possible, the 4 tasks with wrong tests", pos[pos.task.isin(FLAWED_POSSIBLE)])]:
        for m in MODELS + ["all"]:
            d = d0 if m == "all" else d0[d0.model == m]
            eps = d.groupby(["model", "row"])
            rej_eps = d[d.n_rej >= 1][["model", "row"]].drop_duplicates()
            out[f"{group} | {m}"] = dict(
                episodes=int(eps.ngroups), episodes_rejected=len(rej_eps),
                episodes_with_A=int(d[d.event == 1][["model", "row"]].drop_duplicates().shape[0]),
                before_any_rejection=[int(d[d.n_rej == 0].event.sum()), int((d.n_rej == 0).sum())],
                after_a_rejection=[int(d[d.n_rej >= 1].event.sum()), int((d.n_rej >= 1).sum())],
                turn_right_after_a_rejection=[int(d[d.just_rej].event.sum()), int(d.just_rej.sum())])
    return out


if __name__ == "__main__":
    if sys.argv[1] == "label":
        label_missing(float(sys.argv[2]))
        sys.exit()
    t, _ = load(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    res = dict(part1_own_fail_vs_rejection=part1(t), part2_pass_vs_stop=part2(), part3_possible=part3(t))
    (out / "review_v2.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
