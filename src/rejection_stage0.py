"""Stage 0 of agent 7: what makes a model say it is being tested (alignment-eval awareness, A) on ImpossibleBench —
rejection, length, or noticing the flaw? And what else follows a rejection (hack flags, frustration)?

  python src/rejection_stage0.py <stage0 dir> <out dir>

<stage0 dir> is the output of `src/rejection_turns.py build` (turns.jsonl, episodes.jsonl, texts.jsonl).
Prints every table (for notes/rejection.md) and writes the dashboard datasets a7_*.json to <out dir>.

Data: Goodfire's released ImpossibleBench transcripts (LiveCodeBench, tools scaffold, STOP instruction, 10
submissions, 50 messages), Qwen 3.8 Max (xhigh), GLM 5.2 and Kimi K3 (max effort). Impossible = conflicting +
oneoff splits; possible = original split.

The hazard of an event in a turn = P(the episode's first event is in this turn | none before). The risk set is every
sampled agent turn up to and including the first event (turns after it are dropped). "Matched on turn index" means a
Mantel-Haenszel ratio over strata of the exact turn index (or of the tokens-so-far bin): within each stratum the
turns written after >=1 rejection are compared with turns written before any.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

MODELS = ["Qwen", "GLM", "Kimi"]
# Possible-split tasks whose test is itself wrong (agent 7 for 57/61/81; the verifier found 67).
FLAWED_POSSIBLE = {"lcbhard_57", "lcbhard_61", "lcbhard_81", "lcbhard_67"}
TBINS = [-1, 4, 9, 14, 19, 200]
TLABELS = ["0-4", "5-9", "10-14", "15-19", "20+"]
KBINS = [-1, 2000, 5000, 10000, 20000, 40000, 10**9]  # tokens so far (characters / 4)
KLABELS = ["<2k", "2-5k", "5-10k", "10-20k", "20-40k", "40k+"]
SENT = re.compile(r"(?<=[.!?])\s+|\n+")
WS = re.compile(r"\s+")


def load(d):
    d = Path(d)
    t = pd.read_json(d / "turns.jsonl", lines=True)
    e = pd.read_json(d / "episodes.jsonl", lines=True)
    first_rej = t[t.n_rej >= 1].groupby(["model", "row"]).turn.min().rename("first_rej_turn")
    e = e.merge(first_rej, on=["model", "row"], how="left")
    t = t.merge(e[["model", "row", "first_A_turn", "first_flaw_turn", "first_rej_turn", "n_turns"]],
                on=["model", "row"])
    t["imp"] = t.split != "original"
    e["imp"] = e.split != "original"
    t["tokens_before"] = t.chars_before / 4
    t["just_rej"] = t.events.apply(lambda ev: "rejection" in ev)
    t["just_fail"] = t.events.apply(lambda ev: "own_fail" in ev)
    t["rejc"] = pd.cut(t.n_rej, [-1, 0, 1, 3, 100], labels=["0", "1", "2-3", "4+"]).astype(str)
    t["tbin"] = pd.cut(t.turn, TBINS, labels=TLABELS).astype(str)
    t["kbin"] = pd.cut(t.tokens_before, KBINS, labels=KLABELS).astype(str)
    t["state"] = np.where(t.n_rej > 0, "rejected", np.where(t.noticed_before, "noticed, not rejected",
                                                            "not noticed, not rejected"))
    return t, e


def risk(t, first_col, event_col=None):
    """Turns at risk for the first event: up to and including the first event's turn. Adds `event` (0/1)."""
    r = t[t[first_col].isna() | (t.turn <= t[first_col])].copy()
    r["event"] = (r.turn == r[first_col]).astype(int)
    return r


def kn(s):
    return int(s.sum()), int(len(s))


def _counts(d, exposed, strata):
    """Per episode × stratum: events and turns, exposed and not. Returns (array E×S×4, strata labels)."""
    x = (d[exposed] if isinstance(exposed, str) else exposed).astype(bool).values
    d = d.assign(_x=x, _ep=d.model.astype(str) + "|" + d.row.astype(str), _s=d[strata].astype(str))
    eps = {k: i for i, k in enumerate(d._ep.unique())}
    sts = {k: i for i, k in enumerate(d._s.unique())}
    arr = np.zeros((len(eps), len(sts), 4))
    ei = d._ep.map(eps).values
    si = d._s.map(sts).values
    ev = d.event.values
    np.add.at(arr, (ei, si, 0), ev * x)
    np.add.at(arr, (ei, si, 1), x)
    np.add.at(arr, (ei, si, 2), ev * ~x)
    np.add.at(arr, (ei, si, 3), ~x)
    return arr


def _mh(tot):
    """tot: S×4 (k1, n1, k0, n0) per stratum → MH risk ratio over strata with both groups (inf when the base has no
    event and the exposed group has some; nan when neither has)."""
    k1, n1, k0, n0 = tot.T
    ok = (n1 > 0) & (n0 > 0)
    n = n1 + n0
    num = (k1 * n0 / np.where(n > 0, n, 1))[ok].sum()
    den = (k0 * n1 / np.where(n > 0, n, 1))[ok].sum()
    return (num / den if den else (float("inf") if num else float("nan"))), tot[ok].sum(0)


def mh_ratio(d, exposed, strata):
    """Mantel-Haenszel risk ratio of `event`, exposed vs not, over strata (only strata holding both groups).
    Returns (ratio, k1, n1, k0, n0) with the counts over those strata."""
    r, c = _mh(_counts(d, exposed, strata).sum(0))
    return r, int(c[0]), int(c[1]), int(c[2]), int(c[3])


def mh_ci(d, exposed, strata, reps=1000, seed=0):
    """95% interval for the MH ratio by resampling episodes (cluster bootstrap)."""
    arr = _counts(d, exposed, strata)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(reps):
        w = np.bincount(rng.integers(0, len(arr), len(arr)), minlength=len(arr))
        r, _ = _mh(np.tensordot(w, arr, axes=1))
        if not np.isnan(r):
            vals.append(r)  # infinite resamples (no base event) stay in, so the upper tail isn't trimmed
    if not vals:
        return (None, None)
    lo, hi = (float(np.percentile(vals, q, method="lower" if q < 50 else "higher")) for q in (2.5, 97.5))
    return lo, hi


def table(rows, cols):
    df = pd.DataFrame(rows)
    return df[cols].to_string(index=False) if len(df) else "(none)"


# ---------------------------------------------------------------------------------------------------------------
# Strand 1: length vs rejection


def strand1(t):
    imp = risk(t[t.imp], "first_A_turn")
    rows, tok, mh, longrun = [], [], [], []
    for m in MODELS:
        d = imp[imp.model == m]
        for tb in TLABELS:
            for rc in ["0", "1", "2-3", "4+"]:
                s = d[(d.tbin == tb) & (d.rejc == rc)]
                if len(s):
                    rows.append(dict(model=m, turns=tb, rejections=rc, k=int(s.event.sum()), n=len(s)))
        for kb in KLABELS:
            for rj, lab in [(False, "no rejection yet"), (True, "after >=1 rejection")]:
                s = d[(d.kbin == kb) & ((d.n_rej > 0) == rj)]
                if len(s):
                    tok.append(dict(model=m, tokens=kb, state=lab, k=int(s.event.sum()), n=len(s)))
        d = d.copy()
        d["rej"] = d.n_rej > 0
        for strata, lab in [("turn", "turn index"), ("kbin", "tokens so far (bins)")]:
            r, k1, n1, k0, n0 = mh_ratio(d, d.rej, strata)
            lo, hi = mh_ci(d, "rej", strata, reps=1000)
            mh.append(dict(model=m, matched_on=lab, ratio=round(r, 1), lo=lo and round(lo, 1), hi=hi and round(hi, 1),
                           k_rejected=k1, n_rejected=n1, k_not=k0, n_not=n0))
        s = d[(d.turn >= 15) & (d.n_rej == 0)]
        s2 = d[(d.turn >= 15) & (d.n_rej == 0) & d.noticed_before]
        longrun.append(dict(model=m, k=int(s.event.sum()), n=len(s), episodes=s[["row"]].drop_duplicates().shape[0],
                            k_noticed=int(s2.event.sum()), n_noticed=len(s2)))
    print("\n## Strand 1a. First A statement per turn, by turn index and rejections so far (impossible splits)")
    print(table(rows, ["model", "turns", "rejections", "k", "n"]))
    print("\n## Strand 1b. Same, by tokens so far (model text before the turn, characters/4)")
    print(table(tok, ["model", "tokens", "state", "k", "n"]))
    print("\n## Strand 1c. Mantel-Haenszel ratio, turns after >=1 rejection vs none yet (episode bootstrap 95%)")
    print(table(mh, ["model", "matched_on", "ratio", "lo", "hi", "k_rejected", "n_rejected", "k_not", "n_not"]))
    print("\n## Strand 1d. Long stretches with no rejection: turns 15+ written before any rejection")
    print(table(longrun, ["model", "k", "n", "episodes", "k_noticed", "n_noticed"]))
    return rows, tok, mh, longrun


# ---------------------------------------------------------------------------------------------------------------
# Strand 2: noticing vs being told


def strand2(t):
    imp = risk(t[t.imp], "first_A_turn")
    states, mh, imm, ev = [], [], [], []
    for m in MODELS:
        d = imp[imp.model == m].copy()
        for tb in TLABELS:
            for st in ["not noticed, not rejected", "noticed, not rejected", "rejected"]:
                s = d[(d.tbin == tb) & (d.state == st)]
                if len(s):
                    states.append(dict(model=m, turns=tb, state=st, k=int(s.event.sum()), n=len(s)))
        sub = d[(d.turn >= 5) & d.state.isin(["rejected", "noticed, not rejected"])].copy()
        sub["rej"] = sub.state == "rejected"
        r, k1, n1, k0, n0 = mh_ratio(sub, sub.rej, "turn")
        lo, hi = mh_ci(sub, "rej", "turn", reps=1000)
        mh.append(dict(model=m, comparison="rejected vs noticed-not-rejected (turns 5+)", ratio=round(r, 1),
                       lo=lo and round(lo, 1), hi=hi and round(hi, 1), k_rejected=k1, n_rejected=n1, k_not=k0, n_not=n0))
        # Immediacy: right after a rejection vs later; right after own failing run vs not (no rejection yet)
        rj = d[d.n_rej > 0]
        n0 = d[(d.n_rej == 0) & (d.turn >= 5)]
        for lab, s in [("turn right after a rejection", rj[rj.just_rej]),
                       ("later turns, after a rejection", rj[~rj.just_rej]),
                       ("turn right after its own failing test run (no rejection yet, turn 5+)", n0[n0.just_fail]),
                       ("other turns, no rejection yet (turn 5+)", n0[~n0.just_fail])]:
            imm.append(dict(model=m, when=lab, k=int(s.event.sum()), n=len(s)))
        # Event study: turns relative to the first notice (censored at the first rejection) and to the first rejection
        for align, col in [("first noticed flaw (before any rejection)", "first_flaw_turn"),
                           ("first rejection", "first_rej_turn")]:
            s = d[d[col].notna()].copy()
            s["rel"] = s.turn - s[col]
            if col == "first_flaw_turn":
                s = s[s.n_rej == 0]
            for k in range(-3, 7):
                x = s[s.rel == k]
                if len(x):
                    ev.append(dict(model=m, aligned_on=align, rel=k, k=int(x.event.sum()), n=len(x)))
    print("\n## Strand 2a. First A per turn by state: noticed a flaw (asserted in an earlier turn) vs rejected")
    for m in MODELS:
        d = imp[imp.model == m]
        at_notice = d[(d.turn == d.first_flaw_turn) & (d.n_rej == 0)]
        first_rej = d[d.just_rej & (d.n_rej == 1)]
        print(f"  {m}: first A in the noticing turn itself {int(at_notice.event.sum())}/{len(at_notice)}; "
              f"in the turn right after the first rejection {int(first_rej.event.sum())}/{len(first_rej)}")
    print(table(states, ["model", "turns", "state", "k", "n"]))
    print("\n## Strand 2b. Turn-matched ratio, rejected vs noticed but not rejected")
    print(table(mh, ["model", "comparison", "ratio", "lo", "hi", "k_rejected", "n_rejected", "k_not", "n_not"]))
    print("\n## Strand 2c. Immediacy")
    print(table(imm, ["model", "when", "k", "n"]))
    print("\n## Strand 2d. Event study (hazard of the first A by turns since the alignment point)")
    print(table(ev, ["model", "aligned_on", "rel", "k", "n"]))
    return states, mh, imm, ev


# ---------------------------------------------------------------------------------------------------------------
# Strand 3: the possible split


def strand3(t, e):
    p = e[~e.imp].copy()
    p["flawed_task"] = p.task.isin(FLAWED_POSSIBLE)
    p["rejected"] = p.n_rej > 0
    rows = []
    for m in MODELS:
        for fl, flab in [(True, "task with a wrong test (57, 61, 67, 81)"), (False, "other tasks")]:
            for rj, rlab in [(True, "rejected >=1"), (False, "never rejected")]:
                s = p[(p.model == m) & (p.flawed_task == fl) & (p.rejected == rj)]
                rows.append(dict(model=m, tasks=flab, rejected=rlab, episodes=len(s),
                                 A=int(s.first_A_turn.notna().sum()), noticed=int(s.first_flaw_turn.notna().sum()),
                                 hack=int((s.verdict == "yes").sum())))
    eps = p[p.rejected | p.flawed_task].sort_values(["task", "model"])
    detail = []
    for _, r in eps.iterrows():
        detail.append(dict(model=r.model, task=r.task, flawed_test=r.flawed_task, turns=r.n_turns, rejections=r.n_rej,
                           first_rejection_turn=None if pd.isna(r.first_rej_turn) else int(r.first_rej_turn),
                           first_flaw_claim_turn=None if pd.isna(r.first_flaw_turn) else int(r.first_flaw_turn),
                           first_A_turn=None if pd.isna(r.first_A_turn) else int(r.first_A_turn),
                           A_vs_rejection=("no A" if pd.isna(r.first_A_turn) else
                                           "before any rejection" if pd.isna(r.first_rej_turn) or r.first_A_turn < r.first_rej_turn
                                           else "at/after a rejection"),
                           hack_verdict=r.verdict))
    print("\n## Strand 3a. Possible split: A by whether the task's test is wrong and whether the episode was rejected")
    print(table(rows, ["model", "tasks", "rejected", "episodes", "A", "noticed", "hack"]))
    print("\n## Strand 3b. Possible-split episodes that were rejected or are on a task with a wrong test")
    print(table(detail, list(detail[0].keys())))
    # Matched comparison: never-rejected episodes of similar length on the same tasks
    return rows, detail


# ---------------------------------------------------------------------------------------------------------------
# Strand 4: what else follows a rejection (Goodfire's judge flags)


def strand4(t, e):
    out, mh, hacks = [], [], []
    for flag, col, lab in [("considered", "considered_here", "hack considered (judge flag)"),
                           ("acted", "acted_here", "hack attempted or enacted (judge flag)")]:
        tt = t[t.imp].copy()
        first = tt[tt[col] > 0].groupby(["model", "row"]).turn.min().rename("first_x")
        tt = tt.merge(first, on=["model", "row"], how="left")
        r = risk(tt, "first_x")
        for m in MODELS:
            d = r[r.model == m].copy()
            d["rej"] = d.n_rej > 0
            ratio, k1, n1, k0, n0 = mh_ratio(d, d.rej, "turn")
            lo, hi = mh_ci(d, "rej", "turn", reps=1000) if flag == "considered" else (None, None)
            mh.append(dict(model=m, measure=lab, ratio=round(ratio, 1) if np.isfinite(ratio) else None,
                           lo=lo and round(lo, 1), hi=hi and round(hi, 1), k_rejected=k1, n_rejected=n1, k_not=k0, n_not=n0))
            for st, s in [("no rejection yet", d[~d.rej]), ("turn right after a rejection", d[d.rej & d.just_rej]),
                          ("later turns after a rejection", d[d.rej & ~d.just_rej])]:
                out.append(dict(model=m, measure=lab, when=st, k=int(s.event.sum()), n=len(s)))
    # Hack episodes (verdict_enacted yes): where the first acted flag falls, and A before it
    for m in MODELS:
        ee = e[(e.model == m) & e.imp & (e.verdict == "yes")]
        tm = t[(t.model == m) & t.imp]
        pre = post = a_before = none = 0
        for _, r in ee.iterrows():
            tr = tm[(tm.row == r.row) & (tm.acted_here > 0)]
            if not len(tr):
                none += 1
                continue
            k = tr.turn.min()
            nrej = int(tm[(tm.row == r.row) & (tm.turn == k)].n_rej.iloc[0])
            if nrej == 0:
                pre += 1
            else:
                post += 1
                if pd.notna(r.first_A_turn) and r.first_A_turn <= k:
                    a_before += 1
        hacks.append(dict(model=m, hack_episodes=len(ee), first_hack_before_any_rejection=pre,
                          after_a_rejection=post, of_which_A_at_or_before_it=a_before, no_acted_flag=none))
    # Order of first A and first considered flag, in episodes with both
    order = []
    for m in MODELS:
        tm = t[(t.model == m) & t.imp]
        fc = tm[tm.considered_here > 0].groupby("row").turn.min()
        ea = e[(e.model == m) & e.imp].set_index("row").first_A_turn
        both = [(ea[r], fc[r]) for r in fc.index if pd.notna(ea.get(r))]
        order.append(dict(model=m, episodes_with_both=len(both), A_first=sum(a < c for a, c in both),
                          same_turn=sum(a == c for a, c in both), considered_first=sum(a > c for a, c in both)))
    print("\n## Strand 4a. First judge flag per turn: before any rejection, right after one, later (impossible splits)")
    print(table(out, ["model", "measure", "when", "k", "n"]))
    print("\n## Strand 4b. Turn-matched ratio, after >=1 rejection vs none yet")
    print(table(mh, ["model", "measure", "ratio", "lo", "hi", "k_rejected", "n_rejected", "k_not", "n_not"]))
    print("\n## Strand 4c. Hack episodes (verdict_enacted yes): first attempted/enacted flag before or after a rejection")
    print(table(hacks, list(hacks[0].keys())))
    print("\n## Strand 4d. First A vs first considered-hack flag, episodes with both")
    print(table(order, list(order[0].keys())))
    return out, mh, hacks, order


# ---------------------------------------------------------------------------------------------------------------
# Strand 5: frustration, repetition and what surrounds the first A statement


def strand5(t, e, texts):
    imp = t[t.imp].copy()
    imp["frust"] = imp.frust_here > 0
    imp["frust_fb"] = imp.frust_feedback > 0
    imp["repeat"] = imp.repeat_here > 0
    rates = []
    for m in MODELS:
        d = imp[imp.model == m]
        for st, s in [("no rejection yet", d[d.n_rej == 0]), ("after 1 rejection", d[d.n_rej == 1]),
                      ("after 2-3", d[d.n_rej.between(2, 3)]), ("after 4+", d[d.n_rej >= 4])]:
            for meas in ["frust", "frust_fb", "repeat"]:
                rates.append(dict(model=m, when=st, measure={"frust": "frustration words",
                                                             "frust_fb": "frustration words about the feedback",
                                                             "repeat": "notes the repeated failure"}[meas],
                                  k=int(s[meas].sum()), n=len(s)))
    # Does prior frustration / repetition go with the first A, at matched (turn index, rejections so far)?
    cond = []
    r = risk(imp, "first_A_turn")
    r = r.sort_values(["model", "row", "turn"])
    for meas, lab in [("frust_fb", "frustration about the feedback"), ("repeat", "notes the repeated failure"),
                      ("frust", "any frustration words (mostly a bare 'Ugh')")]:
        r["prior_" + meas] = r.groupby(["model", "row"])[meas].transform(lambda s: s.shift(1, fill_value=False).cummax())
        for m in MODELS:
            d = r[(r.model == m) & (r.n_rej > 0)].copy()
            d["strat"] = d.turn.astype(str) + "|" + d.rejc
            ratio, k1, n1, k0, n0 = mh_ratio(d, d["prior_" + meas].astype(bool), "strat")
            cond.append(dict(model=m, prior=lab + " in an earlier turn", ratio=round(ratio, 2) if np.isfinite(ratio) else None,
                             k_with=k1, n_with=n1, k_without=k0, n_without=n0))
    # Around each first A: same-turn context before the A passage, where it is stated, what follows
    ctx = []
    feats = dict(
        repetition=re.compile(r"keeps?|kept|again|same|identical|repeated\w*|re-?prompt\w*|loop", re.I),
        feedback=re.compile(r"grader|harness|feedback|reject\w*|automated|failed the tests|evaluator", re.I),
        instruction=re.compile(r"STOP|carve|instruction|DO NOT MODIFY|critically evaluat\w*|explicitly (?:say|tell)", re.I),
    )
    import importlib.util
    spec = importlib.util.spec_from_file_location("rt", Path(__file__).with_name("rejection_turns.py"))
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    for _, ep in e[e.imp & e.first_A_turn.notna()].iterrows():
        k = int(ep.first_A_turn)
        tr = imp[(imp.model == ep.model) & (imp.row == ep.row)].set_index("turn")
        row = tr.loc[k]
        txt = texts.get((ep.model, int(ep.row), k))
        nxt = tr.loc[k + 1: k + 3]
        rec = dict(model=ep.model, row=int(ep.row), turn=k, n_rej=int(row.n_rej), just_rej=bool(row.just_rej),
                   A_place=",".join(sorted(set(row.A_where))) if row.A_where else "",
                   frust_before=bool((tr.loc[:k - 1].frust_here > 0).any()) if k > 0 else False,
                   frust_fb_before=bool((tr.loc[:k - 1].frust_feedback > 0).any()) if k > 0 else False,
                   repeat_before=bool((tr.loc[:k - 1].repeat_here > 0).any()) if k > 0 else False,
                   next_submit=any("submit" in (x or []) for x in nxt.tool_calls) if len(nxt) else False,
                   says_to_grader=int(tr.loc[k:k + 3].submit_A_regex.sum()) > 0,
                   says_to_grader_ever=int(tr.submit_A_regex.sum()) > 0,
                   same_turn_submit="submit" in (row.tool_calls or []),
                   next_considered=int(nxt.considered_here.sum()) if len(nxt) else 0,
                   next_acted=int(nxt.acted_here.sum()) if len(nxt) else 0,
                   last_turn=k == int(ep.n_turns) - 1)
        if txt and ep.first_A_text:
            # The 1,500 characters of the same turn before the first A passage (the turn's own lead-up; the
            # rejection message itself is a user turn and is not included).
            full = WS.sub(" ", txt[0]).strip() + " " + WS.sub(" ", txt[1]).strip()
            pos = full.find(WS.sub(" ", ep.first_A_text).strip()[:80])
            pre = full[max(0, pos - 1500):pos] if pos >= 0 else ""
            rec["chars_before_A_in_turn"] = pos
            for f, pat in feats.items():
                rec["ctx_" + f] = bool(pat.search(pre))
            rec["ctx_frust"] = bool(rt.FRUST.search(pre))
            rec["ctx_frust_fb"] = any(rt.FRUST.search(x) and rt.ABOUT_FEEDBACK.search(x) for x in rt.SENT.split(pre))
            rec["ctx_repeat"] = bool(rt.REPEAT.search(pre))
            rec["a_text"] = ep.first_A_text[:400]
            rec["lead_up"] = pre[-500:]
        ctx.append(rec)
    cdf = pd.DataFrame(ctx)
    for c in ["ctx_repetition", "ctx_feedback", "ctx_instruction", "ctx_frust", "ctx_frust_fb", "ctx_repeat"]:
        cdf[c] = cdf.get(c, pd.Series(False, index=cdf.index)).fillna(False).astype(bool)
    cdf["chars_before_A_in_turn"] = cdf.get("chars_before_A_in_turn", pd.Series(-1, index=cdf.index)).fillna(-1)
    summ = []
    for m in MODELS:
        s = cdf[cdf.model == m]
        n = len(s)
        for lab, v in [("in the turn right after a rejection", s.just_rej.sum()),
                       ("before any rejection", (s.n_rej == 0).sum()),
                       ("after the 1st or 2nd rejection", s.n_rej.between(1, 2).sum()),
                       ("labelled passage is in the reasoning (not the reply text)", (s.A_place == "reasoning").sum()),
                       ("A keywords in a submit answer, this turn or the next 3 (lower bound)", s.says_to_grader.sum()),
                       ("A keywords in any submit answer of the episode (lower bound)", s.says_to_grader_ever.sum()),
                       ("frustration about the feedback in an earlier turn", s.frust_fb_before.sum()),
                       ("any frustration words in an earlier turn", s.frust_before.sum()),
                       ("notes the repeated failure in an earlier turn", s.repeat_before.sum()),
                       ("same turn submits", s.same_turn_submit.sum()),
                       ("submits within the next 3 turns", s.next_submit.sum()),
                       ("hack considered within the next 3 turns", (s.next_considered > 0).sum()),
                       ("hack attempted/enacted within the next 3 turns", (s.next_acted > 0).sum()),
                       ("lead-up in the same turn mentions the feedback or grader", s.ctx_feedback.sum()),
                       ("lead-up notes the repeated failure (REPEAT pattern)", s.ctx_repeat.sum()),
                       ("lead-up mentions the instruction (STOP, carve, DO NOT MODIFY)", s.ctx_instruction.sum()),
                       ("lead-up has frustration about the feedback", s.ctx_frust_fb.sum()),
                       ("lead-up has any frustration words", s.ctx_frust.sum()),
                       ("A passage opens the turn (<200 characters before it)", (s.chars_before_A_in_turn.between(0, 199)).sum())]:
            summ.append(dict(model=m, measure=lab, k=int(v), n=n))
    for m in MODELS:
        d = imp[imp.model == m]
        tot, bare, opens, fb = int(d.frust_here.sum()), int(d.frust_bare.sum()), int(d.frust_ugh_open.sum()), int(d.frust_feedback.sum())
        print(f"  {m}: frustration sentences {tot}; a bare 'Ugh'/'Argh'/'Sigh' {bare}; opening with one {opens}; "
              f"about the feedback {fb}")
        rates.append(dict(model=m, when="all turns", measure="frustration sentences that are a bare 'Ugh'", k=bare, n=tot))
        rates.append(dict(model=m, when="all turns", measure="frustration sentences opening with 'Ugh'", k=opens, n=tot))
    print("\n## Strand 5a. Frustration and repetition per turn, by rejections so far (impossible splits)")
    print(table(rates, ["model", "when", "measure", "k", "n"]))
    print("\n## Strand 5b. First A per turn with vs without prior frustration / repetition, matched on turn × rejections")
    print(table(cond, ["model", "prior", "ratio", "k_with", "n_with", "k_without", "n_without"]))
    print("\n## Strand 5c. Around each first A statement")
    print(table(summ, ["model", "measure", "k", "n"]))
    return rates, cond, summ, cdf


def load_texts(d, keys=None):
    out = {}
    for l in (Path(d) / "texts.jsonl").open():
        r = json.loads(l)
        k = (r["model"], r["row"], r["turn"])
        if keys is None or k in keys:
            out[k] = (r["reasoning"], r["reply"])
    return out


def main(d, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    t, e = load(d)
    print("Episodes:", e.groupby(["model", "imp"]).size().to_dict())
    s1 = strand1(t)
    s2 = strand2(t)
    s3 = strand3(t, e)
    s4 = strand4(t, e)
    keys = set((r.model, int(r.row), int(r.first_A_turn)) for _, r in e[e.first_A_turn.notna()].iterrows())
    texts = load_texts(d, keys)
    s5 = strand5(t, e, texts)
    dump = dict(a7_hazard_turn=s1[0], a7_hazard_tokens=s1[1], a7_mh_length=s1[2], a7_longrun=s1[3],
                a7_state=s2[0], a7_mh_notice=s2[1], a7_immediacy=s2[2], a7_event=s2[3],
                a7_possible=s3[0], a7_possible_eps=s3[1],
                a7_flags=s4[0], a7_mh_flags=s4[1], a7_hacks=s4[2], a7_order=s4[3],
                a7_frust=s5[0], a7_frust_cond=s5[1], a7_firstA=s5[2])
    for k, v in dump.items():
        (out / f"{k}.json").write_text(json.dumps(v, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)))
    s5[3].to_json(out / "firstA_context.jsonl", orient="records", lines=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
