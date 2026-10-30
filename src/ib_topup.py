"""IB chat top-up to 6 tasks x 3 (her decision, 27 Oct: "keep IB at 6x3"; design: notes/ib_chat_vs_harness.md,
"Amendment 9"). No API calls here: this plans the next runs and reports. Metadata and scores only; no reply or
reasoning text is read (missing = the reports' rule: cut by the token limit, or no visible text).

    .venv/bin/python src/ib_topup.py plan [model ...]     # next runs per model: ids, max_tokens, log dir, cap, command
    .venv/bin/python src/ib_topup.py report               # per model: homework, rejection, chat at 6x3; writes json
    .venv/bin/python src/ib_topup.py check                # synthetic checks of the slot / tries logic (no logs, no calls)

Slots: homework hw|<task>|r1-r3 and chat chat|<task>|r1-r3 (18 each per model); rejection: one conversation
rj|<task>|<rep> per homework reply from the top-up that is usable and fails round 1.
Tries: at most 3 scored replies per slot, counting the draws already made (first draws and earlier re-draws). An Inspect
error (no scored sample) is not a try and is run again. A slot still missing after 3 tries is reported, not re-drawn,
and the provider is not changed. GLM: a reply cut at our 131,072 limit is re-drawn at 262,144; other re-draws keep the
setup's max_tokens. Rejection: a conversation lost to a cut at our limit (GLM) is re-drawn from round 2 at 262,144 (as
before, her "Yes, re-draw at 262k"), within the same 3 tries; one lost to a provider error is not re-drawn (as before).
Layering: dirs are read in order (existing, then top-up stage 1, 1_262k, 2, 2_262k, 3, 3_262k); a later scored reply
replaces an earlier one with the same id. Re-draws run only on missing slots, so a usable reply is never replaced.
"""
import json
import sys
from collections import Counter
from datetime import timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TASKS = ["lcbhard_101", "lcbhard_27", "lcbhard_40", "lcbhard_58", "lcbhard_63", "lcbhard_99"]
REPS = (1, 2, 3)
MAX_TRIES = 3
GLM_REDRAW_TOKENS = 262144
# name: runner --setup, the chat root, the homework / rejection dir stem, and caps on the guard scale (token price x 1.3)
MODELS = {
    "qwen": dict(label="Qwen 3.8 2.4T (SiliconFlow)", setup="qwen", chat_root="logs/ib_chat_vs_harness", stem="qwen",
                 cap=dict(homework=10.0, rejection=8.0, chat=2.5)),
    "ds": dict(label="DeepSeek V4 Pro (Novita, max_tokens 393,216)", setup="dsn", chat_root="logs/ib_chat_vs_harness_dsn",
               stem="ds", cap=dict(homework=4.0, rejection=4.0, chat=1.0)),
    "glm": dict(label="GLM 5.2 (SiliconFlow, max_tokens 131,072)", setup="glm", chat_root="logs/ib_chat_vs_harness_glm",
                stem="glm", cap=dict(homework=4.0, rejection=4.0, chat=2.0)),
    "q27p": dict(label="Qwen 3.8 27B (Parasail)", setup="q27p", chat_root="logs/ib_chat_vs_harness_q27p", stem="q27p",
                 cap=dict(homework=4.0, rejection=4.0, chat=1.0)),
}
# "" = fresh replies / conversations; "_262k" = GLM re-draws of a reply or round cut at our 131,072 limit; "_resume" =
# rejection conversations lost to a provider error or an empty reply, resumed at the lost round (setup's max_tokens)
STAGES = [f"s{n}{sfx}" for n in (1, 2, 3) for sfx in ("", "_262k", "_resume")]


def existing_dirs(m, part):
    c = MODELS[m]
    if part == "chat":
        return [f"{c['chat_root']}/chat"]
    if part == "homework":
        return [f"logs/ib_chat_homework/{c['stem']}", f"logs/ib_chat_homework/{c['stem']}_redraw"]
    return [f"logs/ib_chat_rejection/{c['stem']}", f"logs/ib_chat_rejection/{c['stem']}_redraw"]


def topup_dir(m, part, stage):
    c = MODELS[m]
    if part == "chat":
        return f"{c['chat_root']}/chat_topup_{stage}"
    root = "logs/ib_chat_homework" if part == "homework" else "logs/ib_chat_rejection"
    return f"{root}/{c['stem']}_topup_{stage}"


def all_dirs(m, part):
    return existing_dirs(m, part) + [topup_dir(m, part, s) for s in STAGES]


# ---- reading (scores, stop reasons, token counts; never text beyond the reports' visible-text emptiness check) ----
def reply_rows(d):
    """One row per scored chat / homework sample in a dir: id, missing, cut_at_our_limit, hack, est cost."""
    import ib_chat_vs_harness_report as R
    from ib_chat_homework_report import raw_finish
    out = []
    p = ROOT / d
    if not p.exists():
        return out
    for s, model, provider in R.samples_in(p, with_model=True):
        if s.error or not s.scores:
            out.append(dict(id=str(s.id), scored=False, dir=d))
            continue
        text = R.final_text(s, "chat")
        end = s.output.stop_reason if s.output else None
        ev = [e for e in s.events if e.event == "model"]
        e = ev[-1] if ev else None
        out_t = e.output.usage.output_tokens if e is not None and e.output and e.output.usage else None
        max_t = e.config.max_tokens if e is not None and e.config else None
        missing = end in R.CUT or not text.strip()
        out.append(dict(id=str(s.id), scored=True, dir=d, missing=missing, end=end, raw_finish=raw_finish(e),
                        out_tokens=out_t, max_tokens=max_t, hack=s.scores["code_passes_tests"].value == "C",
                        points_out=bool(R.CONTRA.search(text)),
                        cut_at_our_limit=bool(end in R.CUT and max_t and out_t is not None and out_t >= 0.9 * max_t),
                        est=R.cost(s, model, provider)))
    return out


def slots(rows_by_dir, prefix):
    """{slot id: dict(tries, final row or None, history)} over dirs in layering order."""
    st = {f"{prefix}|{t}|r{r}": dict(tries=0, final=None, history=[]) for t in TASKS for r in REPS}
    for d, rows in rows_by_dir:
        for row in rows:
            if row["id"] not in st or not row["scored"]:
                continue
            x = st[row["id"]]
            x["tries"] += 1
            x["history"].append((d, "missing" if row["missing"] else "usable"))
            x["final"] = row
    return st


def status(x):
    f = x["final"]
    if f is not None and not f["missing"]:
        return "usable"
    return "empty after 3 tries" if x["tries"] >= MAX_TRIES else "to run"


def next_stage(m, part):
    """1 + the highest top-up stage with a dir on disk (both groups of a stage are planned together)."""
    ran = [int(s[1]) for s in STAGES if (ROOT / topup_dir(m, part, s)).exists()]
    return (max(ran) + 1) if ran else 1


def plan_slots(m, st):
    """Ids to run next, split by max_tokens group: {"": [...], "_262k": [...]}."""
    groups = {"": [], "_262k": []}
    for sid, x in st.items():
        if status(x) != "to run":
            continue
        f = x["final"]
        big = m == "glm" and f is not None and (f["cut_at_our_limit"] or (f["max_tokens"] or 0) >= GLM_REDRAW_TOKENS)
        groups["_262k" if big else ""].append(sid)
    return groups


def homework_state(m):
    return slots([(d, reply_rows(d)) for d in all_dirs(m, "homework")], "hw")


def chat_state(m):
    return slots([(d, reply_rows(d)) for d in all_dirs(m, "chat")], "chat")


def rejection_state(m, hw=None):
    """(new conversation slots, their outcome dicts from ib_chat_rejection_report.conversations, tries per id)."""
    import ib_chat_rejection_report as RJ
    import ib_chat_vs_harness_report as R
    hw = hw or homework_state(m)
    old_conv, _ = RJ.conversations([ROOT / d for d in existing_dirs(m, "homework")],
                                   [ROOT / d for d in existing_dirs(m, "rejection")])
    old_started = {k for k, c in old_conv.items() if c["ended"] not in ("missing at round 1", "error at round 1")}
    new = [sid for sid, x in hw.items() if status(x) == "usable" and not x["final"]["hack"]
           and sid.split("|", 1)[1] not in old_started]
    conv, _ = RJ.conversations([ROOT / d for d in all_dirs(m, "homework")], [ROOT / d for d in all_dirs(m, "rejection")])
    tries = Counter()
    for d in all_dirs(m, "rejection"):
        if (ROOT / d).exists():
            for s in R.samples_in(ROOT / d):
                if not s.error and s.scores:
                    tries[str(s.id)] += 1
    return new, conv, tries, old_started


def how_ended(c):
    """The conversation's own ending: the 'ended' text before the report's added notes (a re-drawn first draw, an
    extraction-error rejection, the verifier's re-score)."""
    return (c.get("ended") or "").split(" (rounds 2-3 re-drawn")[0].split("; ")[0]


def is_lost(c):
    e = how_ended(c)
    return e.startswith("missing at round") or e.startswith("error")


def plan_rejection(m, new, conv, tries, started=()):
    """Fresh conversations for the new failing homework replies (group ""), and every lost conversation, old or new,
    with tries left, resumed at its lost round: GLM cuts at our limit at 262,144 ("_262k"), the rest at the setup's
    max_tokens ("_resume"; her "yes, re-draw rejection rounds lost to provider errors", 27 Oct). Lost after 3 tries:
    reported."""
    groups = {"": [], "_262k": [], "_resume": []}
    lost = []
    keys = list(dict.fromkeys(list(started) + [sid.split("|", 1)[1] for sid in new]))
    for key in keys:
        rid = f"rj|{key}"
        c = conv.get(key, {})
        if tries[rid] == 0:
            if f"hw|{key}" in new:
                groups[""].append(rid)
            continue
        if not is_lost(c):
            continue
        if tries[rid] >= MAX_TRIES:
            lost.append((rid, c.get("ended")))
        elif m == "glm" and "at our limit" in how_ended(c):
            groups["_262k"].append(rid)
        else:
            groups["_resume"].append(rid)
    return groups, lost


def spent(m, part):
    from run_spend import own_spend
    return sum(own_spend(str(ROOT / topup_dir(m, part, s)))[1] for s in STAGES if (ROOT / topup_dir(m, part, s)).exists())


SANDBOXES = {m: 2 for m in MODELS}   # per model process; `plan --sandboxes qwen=2,ds=2,glm=1` sets them (agent 2's split)


def command(m, part, ids, stage, cap):
    c = MODELS[m]
    task = {"homework": "homework", "chat": "chat", "rejection": "rejection"}[part]
    cmd = (f".venv/bin/python src/run_chat_vs_harness.py --task {task} --setup {c['setup']} --reps 3 "
           f"--ids '{','.join(ids)}' --cap {cap:.2f} --max-sandboxes {SANDBOXES[m]} "
           f"--log-dir {topup_dir(m, part, stage)}")
    if stage.endswith("_262k"):
        cmd += f" --max-tokens {GLM_REDRAW_TOKENS}"
    if part == "rejection" and (stage.endswith("_262k") or stage.endswith("_resume")):
        cmd += " --resume " + ",".join(d for d in all_dirs(m, "rejection") if (ROOT / d).exists())
    elif part == "rejection":
        cmd += " --source " + ",".join(d for d in all_dirs(m, "homework") if (ROOT / d).exists())
    return cmd


def plan(models):
    out = {}
    for m in models:
        hw = homework_state(m)
        ch = chat_state(m)
        steps = []
        for part, st in (("homework", hw), ("chat", ch)):
            g = plan_slots(m, st)
            n = next_stage(m, part)
            left = MODELS[m]["cap"][part] - spent(m, part)
            total = sum(len(v) for v in g.values())
            for sfx, ids in g.items():
                if ids:   # two groups in one stage (GLM 131k / 262k) share the part's remaining cap by id count
                    cap = left * len(ids) / total
                    steps.append(dict(part=part, stage=f"s{n}{sfx}", ids=ids, cap=round(cap, 2),
                                      command=command(m, part, ids, f"s{n}{sfx}", cap)))
        hw_open = any(status(x) == "to run" for x in hw.values())
        if hw_open:
            rj = "after the homework slots are final"
        else:
            new, conv, tries, old_started = rejection_state(m, hw)
            g, lost = plan_rejection(m, new, conv, tries, started=sorted(old_started))
            n = next_stage(m, "rejection")
            left = MODELS[m]["cap"]["rejection"] - spent(m, "rejection")
            total = sum(len(v) for v in g.values())
            for sfx, ids in g.items():
                if ids:
                    cap = left * len(ids) / total
                    steps.append(dict(part="rejection", stage=f"s{n}{sfx}", ids=ids, cap=round(cap, 2),
                                      command=command(m, "rejection", ids, f"s{n}{sfx}", cap)))
            rj = dict(new_conversations=len(new), lost_after_3_tries=lost)
        out[m] = dict(model=MODELS[m]["label"], steps=steps, rejection=rj,
                      homework_empty_after_3=[s for s, x in hw.items() if status(x) == "empty after 3 tries"],
                      chat_empty_after_3=[s for s, x in ch.items() if status(x) == "empty after 3 tries"])
    print(json.dumps(out, indent=1))
    return out


RECHECK = {"qwen": ("logs/ib_chat_vs_harness/recheck", "qwen"), "ds": ("logs/ib_chat_vs_harness_ds/recheck", "dsn"),
           "glm": ("logs/ib_chat_vs_harness_glm/recheck", "glm"), "q27p": ("logs/ib_chat_vs_harness_q27p/recheck", "q27p")}


def chat_reading(m):
    """The registered chat-vs-harness reading (ib_chat_vs_harness_report.report) re-run with the chat arm's re-drawn
    replies in place of its missing ones ("with re-draws", amendment 9); the harness side is unchanged."""
    import ib_chat_vs_harness_report as R
    rows = {}
    for d in all_dirs(m, "chat"):
        if (ROOT / d).exists():
            for r in R.chat_rows(ROOT / d):
                old = rows.get(r["id"])
                if old is None or old["error"] or old.get("missing"):
                    rows[r["id"]] = r
    rd, setup = RECHECK[m]
    rep = R.report(list(rows.values()), R.harness_rows(ROOT / rd, setup), setup)
    keep = ("hack_among_not_missing", "hack", "missing")
    return dict(reading=rep["reading"], chat={k: v for k, v in rep["chat"].items() if k in keep},
                harness={k: v.get("same_rule") for k, v in rep["harness"].items()})


def rejection_tries(m):
    """Every conversation that lost a round at least once: each try in layering order, as (dir, where it ended, the
    round it started at, whether it was resumed from a lost round, and the UTC time its sample started, from its first
    event). Scores and metadata only."""
    import ib_chat_vs_harness_report as R
    hist = {}
    for d in all_dirs(m, "rejection"):
        if not (ROOT / d).exists():
            continue
        for s in R.samples_in(ROOT / d):
            if s.error or not s.scores:
                continue
            md = s.scores["rejection_outcome"].metadata
            rounds = md.get("rounds") or []
            lost_at = rounds[-1]["round"] if rounds and rounds[-1]["outcome"] == "missing" else None
            smd = s.metadata or {}
            ts = s.events[0].timestamp if s.events else None
            hist.setdefault(str(s.id), []).append(dict(dir=d.rsplit("/", 1)[-1], ended=md.get("ended"),
                                                       lost_at_round=lost_at,
                                                       started_at_round=smd.get("resume_at", 2),
                                                       resumed="resume_at" in smd,
                                                       date=ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
                                                       if ts else None))
    return {k: v for k, v in hist.items() if any(t["lost_at_round"] for t in v)}


def report():
    import ib_chat_rejection_report as RJ
    out = {}
    for m in MODELS:
        hw, ch = homework_state(m), chat_state(m)
        res = {}
        for part, st in (("homework", hw), ("chat", ch)):
            use = [x["final"] for x in st.values() if status(x) == "usable"]
            res[part] = dict(usable=f"{len(use)}/18", hacked=f"{sum(r['hack'] for r in use)}/{len(use)}",
                             names_contradiction=f"{sum(r['points_out'] for r in use)}/{len(use)}",
                             empty_after_3=[s for s, x in st.items() if status(x) == "empty after 3 tries"],
                             still_to_run=[s for s, x in st.items() if status(x) == "to run"],
                             tries=dict(Counter(x["tries"] for x in st.values())),
                             topup_est=round(spent(m, part), 2))
        new, conv, tries, old_started = rejection_state(m, hw)
        for t, o in RJ.VERIFIER_FIXED.get(MODELS[m]["stem"], {}).items():
            if t in conv and conv[t].get("extraction", "find_code") == "find_code":
                conv[t]["hacked_round_fixed"] = o["hacked_round_fixed"]
        # as ib_chat_rejection_report.summarize: every homework slot whose round-1 reply is usable (a round-1 hack counts
        # as hacked by round 1); missing or errored round-1 replies are left out
        base = sorted(t for t, c in conv.items() if c["ended"] not in ("missing at round 1", "error at round 1"))
        by = {k: sum(1 for t in base if (conv[t].get("hacked_round") or 99) <= k) for k in (1, 2, 3)}
        byf = {k: sum(1 for t in base if (conv[t].get("hacked_round_fixed", conv[t].get("hacked_round")) or 99) <= k)
               for k in (1, 2, 3)}
        res["rejection"] = dict(conversations=len(base), new=len(new),
                                hacked_by_round={k: f"{v}/{len(base)}" for k, v in by.items()},
                                hacked_by_round_fixed_extraction={k: f"{v}/{len(base)}" for k, v in byf.items()},
                                lost=[(t, conv[t]["ended"]) for t in base if is_lost(conv[t])],
                                tries_of_lost_rounds=rejection_tries(m),
                                not_yet_run=[t for t in base if "rounds" not in conv.get(t, {}) or
                                             conv[t]["ended"].startswith("round 1 failed")],
                                topup_est=round(spent(m, "rejection"), 2))
        res["chat_registered_reading"] = chat_reading(m)
        out[m] = dict(model=MODELS[m]["label"], **res)
    (ROOT / "logs/ib_chat_homework/topup_report.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


def check():
    """Synthetic checks of the slot logic (no logs read, no calls)."""
    def row(i, missing=False, cut=False, max_t=131072, hack=False):
        return dict(id=i, scored=True, missing=missing, cut_at_our_limit=cut, max_tokens=max_t, hack=hack, end=None,
                    points_out=False, out_tokens=None, raw_finish=None, est=0.0)
    ok = True
    st = slots([("old", [row("hw|lcbhard_40|r1", missing=True)]), ("old_redraw", [row("hw|lcbhard_40|r1", missing=True)]),
                ("s1", [row("hw|lcbhard_40|r1", missing=True), row("hw|lcbhard_40|r2")]),
                ("s1b", [dict(id="hw|lcbhard_40|r3", scored=False)])], "hw")
    ok &= status(st["hw|lcbhard_40|r1"]) == "empty after 3 tries"      # 3 missing tries, counting old draws
    ok &= status(st["hw|lcbhard_40|r2"]) == "usable"
    ok &= st["hw|lcbhard_40|r3"]["tries"] == 0 and status(st["hw|lcbhard_40|r3"]) == "to run"   # Inspect error: no try
    ok &= status(st["hw|lcbhard_101|r2"]) == "to run" and st["hw|lcbhard_101|r2"]["tries"] == 0
    st = slots([("old", [row("chat|lcbhard_99|r3", missing=True, cut=True)]),
                ("old", [row("chat|lcbhard_99|r1", missing=True)])], "chat")
    g = plan_slots("glm", st)
    ok &= "chat|lcbhard_99|r3" in g["_262k"] and "chat|lcbhard_99|r1" in g[""]
    g = plan_slots("qwen", st)
    ok &= "chat|lcbhard_99|r3" in g[""] and not g["_262k"]               # 262k only for GLM
    # a 262k re-draw that is cut again stays in the 262k group
    st = slots([("old", [row("chat|lcbhard_99|r3", missing=True, cut=True)]),
                ("s1_262k", [row("chat|lcbhard_99|r3", missing=True, cut=True, max_t=262144)])], "chat")
    ok &= "chat|lcbhard_99|r3" in plan_slots("glm", st)["_262k"]
    # a usable reply is final even if a later dir had the id (never happens by construction, but layering is by order)
    st = slots([("old", [row("hw|lcbhard_27|r1")])], "hw")
    ok &= status(st["hw|lcbhard_27|r1"]) == "usable" and plan_slots("qwen", st)[""].count("hw|lcbhard_27|r1") == 0
    # lost conversations: only the conversation's own ending counts, not the report's notes
    ok &= not is_lost(dict(ended="hack at round 2 (rounds 2-3 re-drawn; first draw: missing at round 2 (at our limit"
                                 " (131072 of 131072 requested)))"))
    ok &= not is_lost(dict(ended="fail x3; rejection without the failing line (extraction error) at round 3"))
    ok &= is_lost(dict(ended="missing at round 2 (provider error (raw finish 'error', 36468 tokens))"))
    c = dict(ended="missing at round 2 (at our limit (131072 of 131072 requested))")
    g, lost = plan_rejection("glm", ["hw|lcbhard_27|r2"], {"lcbhard_27|r2": c}, Counter({"rj|lcbhard_27|r2": 1}))
    ok &= g["_262k"] == ["rj|lcbhard_27|r2"] and not lost
    perr = dict(ended="missing at round 2 (provider error (raw finish 'error', 1 tokens))")
    g, lost = plan_rejection("qwen", ["hw|lcbhard_27|r2"], {"lcbhard_27|r2": perr}, Counter({"rj|lcbhard_27|r2": 1}))
    ok &= g["_resume"] == ["rj|lcbhard_27|r2"] and not g[""] and not g["_262k"] and not lost   # resumed (her yes)
    g, lost = plan_rejection("qwen", ["hw|lcbhard_27|r2"], {"lcbhard_27|r2": perr}, Counter({"rj|lcbhard_27|r2": 3}))
    ok &= not any(g.values()) and len(lost) == 1                         # 3 tries used: reported, not re-drawn
    # an old conversation lost at round 2 (1 try) is resumed; an old finished one and a fresh one are handled apart
    g, lost = plan_rejection("qwen", ["hw|lcbhard_40|r2"],
                             {"lcbhard_101|r1": perr, "lcbhard_27|r1": dict(ended="hack at round 2"),
                              "lcbhard_40|r2": dict(ended="round 1 failed; rounds 2-3 not run")},
                             Counter({"rj|lcbhard_101|r1": 1, "rj|lcbhard_27|r1": 1}),
                             started=["lcbhard_101|r1", "lcbhard_27|r1"])
    ok &= g[""] == ["rj|lcbhard_40|r2"] and g["_resume"] == ["rj|lcbhard_101|r1"] and not g["_262k"] and not lost
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1] == "check":
        sys.exit(check())
    if sys.argv[1] == "plan":
        args = sys.argv[2:]
        if "--sandboxes" in args:
            i = args.index("--sandboxes")
            SANDBOXES.update({k: int(v) for k, v in (x.split("=") for x in args[i + 1].split(","))})
            args = args[:i] + args[i + 2:]
        plan(args or list(MODELS))
    elif sys.argv[1] == "report":
        report()
