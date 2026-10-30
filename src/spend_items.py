"""Spend analysis item table (agent 10, 27 Oct). One row per run or part-run: family, item, owner, period, $, basis,
class, outcome. Amounts come from agent 2's run ledger (after 23 Oct 14:26Z), my header-only log scan (before it), and
the owners' own recounts where they corrected the scan. Writes notes/spend_analysis_items.csv and prints the tables.

basis: billed = usage.cost; est = Inspect/watchdog token estimate, stored x 1.3 (overstates; list price = /1.3); key = watchdog key-usage rise (upper bound);
       notes = owner's notes, not in any log file; unlogged = owner's estimate of spend in no log (in-flight losses).
class: a result | b null / couldn't use / gate | c waste | p pending (running, or awaiting her check) | u untraced.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

LEDGER = Path("/Users/biancaganescu/Code/split-brain-hypothesis/.claude/worktrees/agent-2-ib-cues/monitor/run_ledger_export.csv")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
P1, P2 = "before", "after"
rows = []


def norm_owner(o):
    import re
    if "orchestrator" in o:
        return "orchestrator"
    m = re.search(r"agent[ -](\d+)\b", o) or re.search(r"\(agent (\d+)\)", o)
    if m:
        return f"agent {m.group(1)}"
    return {"Low-stakes vs high-stakes model behavior 6": "agent 6"}.get(o, o)


CAUSE = {}  # item -> cause, for class c rows


def add(family, item, owner, period, usd, basis, cls, outcome, source):
    rows.append(dict(family=family, item=item, owner=norm_owner(owner), period=period, usd=round(float(usd), 4),
                     basis=basis, cls=cls, cause="", outcome=outcome, source=source))


# ---------------- before 23 Oct 14:26Z ----------------
F = "IB: Goodfire-setup pilots (20 Oct)"
S = "agent 10 log scan; notes/pilot_results.md"
add(F, "effort_pilot", "main session", P1, 2.47, "est", "a", "setup: the 10 tasks used in every later IB run (1g)", S)
add(F, "automated_pass", "main session", P1, 6.49, "est", "a", "1g: no STOP 6/10 vs Goodfire STOP 0/10", S)
add(F, "27b_stop_vs_pass (stopped by her at 15/30 once clear)", "main session", P1, 4.20, "est", "a", "1g: 27B 0/10 vs 5/5", S)
add(F, "student_pass (interview framing)", "main session", P1, 5.40, "est", "b", "0/10 vs 6/10 but more suspicion and lower stakes (confounded); not in the 24 Oct summary", S)
F = "Other envs (our scenarios, D1, provenance, norvane)"
add(F, "mini_b1d1 (first B1/D1 run)", "main session", P1, 1.16, "est", "b", "harness lessons (50-message limit, list crash); D1 later dropped", S)

F = "IB: cue screens"
S = "agent 2's recount (27 Oct), logs/ib_cues"
add(F, "stage 0 cue labels (Luna)", "agent 2", P1, 0.31, "notes", "a", "rows 2a/2g", S)
add(F, "round 1 batch A", "agent 2", P1, 9.55, "est", "a", "3c; 1g", S)
add(F, "round 1 batch B", "agent 2", P1, 7.87, "est", "a", "3c; 1g", S)
add(F, "reflex-rate labels (Luna)", "agent 2", P1, 1.83, "billed", "b", "descriptive table, n=2 per variant; no map row", S)
add(F, "STOP x framing replication (round1c)", "agent 2", P1, 4.53, "est", "a", "1g time-matched grid", S)
add(F, "round1c lost at her 19:24 pause", "agent 2", P1, 0.96, "unlogged", "c", "in-flight work lost (in no log)", S)
add(F, "H_network first try (connection error at the pause)", "agent 2", P1, 0.17, "est", "c", "in-flight work lost", S)
add(F, "H_network re-run, exact Goodfire, H_base, H_neither, STOP+framing", "agent 2", P1, 1.34 + 0.94 + 2.62 + 1.45 + 1.76, "est", "a", "3c network line; 1g grid", S)
add(F, "1g scale-up launch 1 (SIGINT)", "agent 2", P1, 2.06, "est", "c", "superseded: our design fault (one task per cell, front-loaded)", S)
add(F, "1g scale-up launch 2 + A labels", "agent 2", P1, 22.38, "est", "a", "1g: automated grader without STOP 10/20 vs 13/20 (null)", S)
add(F, "1g A labels", "agent 2", P1, 0.18, "notes", "a", "1g", S)
F = "SWE-V / DeepSWE"
add(F, "SWE-V feasibility + screen (agent 2)", "agent 2", P1, 0.064 + 3.13, "billed", "b", "informative null: 20/20 resolved, no test edits; no map row", S)
add(F, "DeepSWE 5 episodes + speed probes/labels", "agent 2", P1, 12.01 + 0.048 + 0.02, "billed", "b", "no rule-visible hack; acquisition 1/5; no map row", S)
add(F, "DeepSWE first runs stalled by sleep", "agent 2", P1, 0.49, "billed", "c", "in-flight work lost (Mac sleep, client timeout)", S)
add(F, "DeepSWE timed-out calls", "agent 2", P1, 0.30, "unlogged", "c", "in-flight work lost (estimate)", S)

F = "IB: persistence and momentum (agent 4)"
S = "agent 4's reply; notes/ib_persistence.md; agent 10 log scan for Inspect"
add(F, "labelling: awareness fill-in, labeller dev, step 2 + IB 2nd pass, 2e labels", "agent 4", P1, 1.14 + 2.6 + 6.34 + 2.21 + 0.41, "billed", "a", "§1-3; feeds §6-7 reflex vs pursuit (claim 3); 2e", S)
add(F, "labelling: unquoted zsh variable sent a full-episode Sol run", "agent 4", P1, 2.04, "billed", "c", "re-run from our bug", S)
add(F, "labelling: stopped v3.3 sample run", "agent 4", P1, 0.74, "billed", "c", "superseded by v3.5", S)
add(F, "labelling: step 3, run 1 labels", "agent 4", P1, 1.5 + 0.92, "billed", "b", "step 3 null; run 1 inconclusive", S)
add(F, "labelling: IB re-flag (not itemised)", "agent 4", P1, 26.32 - (1.14 + 2.6 + 6.34 + 2.21 + 0.41 + 2.04 + 0.74 + 1.5 + 0.92 + 6.79), "billed", "u", "not itemised in agent 4's notes (~$1.7)", S)
add(F, "run 2 effort replay", "agent 4", P1, 6.79, "billed", "b", "inconclusive (manipulation didn't take); used in §6", S)
add(F, "step 3 episodes", "agent 4", P1, 16.83, "est", "b", "no harness variant changed hacking", S)
add(F, "step 3: partial logs / lost in the pause", "agent 4", P1, 17.87 - 16.83, "est", "c", "in-flight work lost (scan $17.87 vs finished $16.83)", S)
add(F, "run 1 recorded20", "agent 4", P1, 19.11, "est", "b", "registered reading inconclusive (p 0.086, 10 pairs)", S)
add(F, "run 1: in flight at the $20 cap", "agent 4", P1, 20.16 - 19.11, "est", "c", "in-flight work lost at the cap", S)
add(F, "run 3 grading_off", "agent 4", P1, 19.45, "est", "a", "0/18 vs 12/18 (1s; precursor of her finding 1)", S)
add(F, "E1 pilot (GLM)", "agent 4", P1, 1.44, "est", "b", "informative null: 0/10 false claims", S)
add(F, "2e orig2e", "agent 4", P1, 8.25, "est", "a", "1r/2e: visible flaw drives weighing (p 0.0078)", S)
add(F, "run 4 grading_off_r4", "agent 4", P1, 19.01, "est", "a", "1s; her finding 1 boxes, chart A (Qwen)", S)

F = "IB: rejection and graded context (agent 7)"
S = "agent 7's reply; notes/rejection.md, phase3_agent7.md"
for it, usd, cls, out in [
    ("stage1/cancelled (relaunched 2 min later)", 0.05, "c", "failed launch, relaunched"),
    ("stage1", 11.57, "a", "2d: the fact of failure matters, not the restated instruction"),
    ("stage1_false (50-message limit)", 4.97, "c", "superseded: re-run at 100 messages"),
    ("stage1_person: L_person", 2.38, "a", "stage 1 table"),
    ("stage1_person: false-reject arm at 50 messages", 3.04, "c", "superseded by the 100-message re-run"),
    ("stage1_m100: lost in the pause", 2.30, "c", "in-flight work lost"),
    ("stage1_m100: saved episode", 3.18 - 2.30, "a", "used in the resume"),
    ("stage1_resume", 11.23, "a", "false rejection doesn't produce 'test of me' (stage 1)"),
    ("graded/d1 C1-C4", 2.39, "c", "superseded: all versions read as a test"),
    ("graded/c5c6 + c5c6_rep", 7.46 + 10.76, "a", "looking graded -> 'test of me' 6/10 vs 1/10"),
    ("c5c6_rep/cancelled (restart for key floor)", 0.43, "c", "failed launch, restarted"),
    ("graded/c9", 3.38, "a", "person's repeated reports -> 'test of me' 0/3 vs 6/7 (tentative)"),
    ("graded/c10", 3.56, "b", "exposure gate failed (0/5 submitted)"),
    ("graded/c5c6_n20", 14.73, "a", "stand-in for the grader 8/20 vs 1/20 (Holm 0.049)"),
    ("graded/c11_valid", 2.74, "b", "validation handed to agent 5; use not recorded"),
    ("graded/g1", 16.86, "b", "informative null: D1 stand-in doesn't generalise"),
    ("graded/c12", 20.85, "b", "in between / not separated"),
    ("graded/g3", 13.89, "b", "inconclusive (p 0.124); led to G3 ext; 1 episode lost to a provider hang"),
    ("graded/g3_ext_aborted", 0.02, "c", "launched before the verifier's OK"),
    ("graded/g3_ext", 12.54, "a", "stand-in aimed at a grader it believes in: 6/8 vs 0/10, p 0.0015"),
]:
    add(F, it, "agent 7", P1, usd, "est", cls, out, S)
add(F, "labelling and C9 probe (results)", "agent 7", P1, 0.88 + 0.81 + 0.46 + 0.02 + 0.07 + 0.07, "billed", "a", "labels behind the stage 1 / graded results", S)
add(F, "labelling for G1, G3, C12", "agent 7", P1, 0.08 + 0.08 + 0.10, "billed", "b", "labels for null cells", S)
add(F, "record usage not itemised", "agent 7", P1, 2.75 - (0.88 + 0.81 + 0.46 + 0.02 + 0.07 + 0.07 + 0.26), "billed", "u", "in the logs, not in agent 7's notes", S)

F = "IB: who reads the reply / forensics (agent 8)"
S = "mats/agent-8-user-facing notes/forensics_no_person.md; agent 10 log scan"
add(F, "exp 1 turn-2 resampling (+labels)", "agent 8", P1, 3.74, "billed", "a", "2o: honest fix 4/15 no reader vs 12/15 a person", S)
add(F, "exp 1c 'saved to a log' (+labels)", "agent 8", P1, 0.81, "billed", "a", "2o: a named reader matters beyond a sentence", S)
add(F, "exp 2 full episodes", "agent 8", P1, 5.02, "est", "b", "no detectable effect at n=4/5; 1 episode lost at the cap ($ not separated)", S)
add(F, "exp 3 watched vs someone to tell (+labels)", "agent 8", P1, 4.56, "billed", "a", "2o: AI reviewer / detector 11/15", S)
add(F, "exp 4 full episodes, three arms", "agent 8", P1, 6.64, "est", "a", "2q (full-episode part not significant)", S)
add(F, "exps 5, 6 second tasks (+labels)", "agent 8", P1, 1.26 + 2.72, "billed", "a", "2o: person effect weak or absent on 2 other tasks", S)
add(F, "exp 7 detector across tasks (+labels)", "agent 8", P1, 5.04, "billed", "a", "2q: 0/44 vs 8/42 hack plans", S)
add(F, "exp 8 detector in full episodes", "agent 8", P1, 7.16 + 6.44, "est", "a", "2q: 0/8 vs 4/8 (p 0.077)", S)
F = "Transcript judges and labels (Goodfire + ours)"
add(F, "tau3/ShoppingBench labelling (parked)", "agent 8", P1, 0.66, "notes", "b", "parked (notes/user_facing.md)", S)
F = "Dark Mode"
S = "logs/aie scan; orchestrator (27 Oct)"
add(F, "puppeteer seeds + seed_g2 (AIE port)", "agent 8", P1, 1.93 + 0.81, "est", "a", "Dark Mode port: led to the 3/5 result (1t, 3h)", S)
add(F, "darkmode_seeds5 episodes", "agent 8", P1, 8.09, "est", "a", "1t/3h: disclosed stand-in plan 3/5 vs 0/5 (tentative)", S)
add(F, "darkmode 2x2 replays + seeds5 saved buffer", "agent 8", P1, 2.96 + 0.55, "billed", "a", "1t/3h", S)
F = "Other envs (our scenarios, D1, provenance, norvane)"
add(F, "norvane pilot", "agent 8", P1, 0.10, "est", "b", "couldn't use: even R reads as a test", S)

F = "Realness probe (agent 5)"
S = "mats/agent-5-grader-definition notes/spend_outcomes_agent5.md"
add(F, "probe rows with a result (Goodfire views, WildChat anchors, SoRH cues, E1, D1 search, 1a, prompt selection)", "agent 5", P1, 29.85, "billed", "a", "tab rows; her 20 SoRH prompts; E1 report; 1a", S)
add(F, "probe gates and nulls (E2-E4, gates, Tier 1 reasoning view 6.29, envs)", "agent 5", P1, 32.10, "billed", "b", "gates answered / informative nulls", S)
add(F, "smoke tests; tau first view dropped mid-run", "agent 5", P1, 0.04 + 0.40, "billed", "c", "setup check; superseded when tau was dropped", S)
add(F, "ledger lines not in agent 5's rows", "agent 5", P1, 62.89 - 62.39, "billed", "u", "in logs/eval_probe ledger; not itemised", S)
add(F, "logs/grader: SoRH grader pilot, shared labeller v3.4 run", "agent 5", P1, 0.42 + 7.00, "billed", "a", "step-1 finding 5; labelled-goal datasets (provisional)", S)
add(F, "logs/grader: labelling prototype", "agent 5", P1, 0.21, "billed", "c", "superseded by the shared labeller", S)

F = "SoRH: cue studies (21-22 Oct)"
S = "agent 1's reply; notes/sorh_cues.md"
add(F, "rounds 1-3, replication, priority test, forensic edits, clean test, 1b test", "agent 1", P1, 7.52 + 33.12, "billed", "a", "sorh_cues §4; 'games the stated metric... 0/40 say tested'; 1b test (b) inside, $ not separated", S)

F = "Transcript judges and labels (Goodfire + ours)"
S = "agent 6's reply; notes/stakes.md, reality.md, tb_shortcuts.md"
add(F, "stakes rubric v1", "agent 6", P1, 0.05, "billed", "c", "superseded the same hour", S)
add(F, "stakes rubric v1.1, stakes reasoning, reality labels, cot v3.4 main", "agent 6", P1, 0.03 + 0.19 + 2.19 + 0.13 + 7.46, "billed", "a", "stakes step 3; map row 3b; reality 5/16", S)
add(F, "cot v3.3 loader test; v3.4 repeat on 2 trials", "agent 6", P1, 0.02 + 0.64, "billed", "b", "tooling check; repeat's use not recorded", S)
F = "tau-bench"
add(F, "tau_framing probe + 3 pilots", "agent 6", P1, 1.17, "billed", "b", "floor effect 0/5 every arm; line closed by her", S)
add(F, "tau banking episode", "agent 6", P1, 0.03, "billed", "c", "failed launch (missing rank_bm25)", S)
F = "Terminal-Bench"
add(F, "cot_labels v3.5 TB phase 2", "agent 6", P1, 1.54, "billed", "a", "tb_shortcuts phase 2: 13/15 vs 2/15", S)

F = "SoRH: multi-turn and persistence (21-22 Oct, agent 3)"
S = "agent 3's recount (27 Oct)"
add(F, "turn-1 selection, rounds, samples, labels, screens A/B, E2-E4, GLM/Kimi, 1b/1k/1l/1p/2i/2j/2r/3e", "agent 3", P1, 98.9 - 3.91 - 0.29, "billed", "a", "map rows 1a 1b 1h 1k 1l 1n 1o 1p 2i 2j 2r 3e (round-2 screen nulls inside, $ not separated)", S)
add(F, "user_reject, 1k-real gate, labeller test", "agent 3", P1, 3.91, "billed", "b", "no capitulation 0/8; gate missed twice", S)
add(F, "raw_excluded re-run; v3.3 partial", "agent 3", P1, 0.17 + 0.12, "billed", "c", "re-run from our scorer bug; stopped to avoid labelling twice", S)

# ---------------- after 23 Oct 14:26Z: agent 2's ledger, owner corrections ----------------
led = {r["name"]: r for r in csv.DictReader(LEDGER.open())}
used = set()


def L(name, family, cls, outcome, usd=None, basis=None, item=None, owner=None):
    r = led[name]
    used.add(name)
    src = r["spend_source"]
    b = basis or ("billed" if src.startswith(("ledger", "record")) else "key" if src.startswith("runner") else "est")
    add(family, item or name, owner or r["owner"], P2,
        float(r["watcher_spend_usd"] or 0) if usd is None else usd, b, cls, outcome, "agent 2's ledger" + ("" if usd is None else " (owner's figure)"))


A1 = "Cues in SoHR agent 1"
F = "SoRH: ablation screen and realness frames (agent 1)"
L("pilot", F, "a", "pipeline gate (method)")
for n in ("pilot_rejudge", "pilot_rejudge_v3", "pilot_rejudge_v4"):
    L(n, F, "b", "failed judge gates -> Sol fallback")
L("pilot_rejudge_sol", F, "a", "v4-sol judges used in every later result")
add(F, "screen: first launch, 20 prompts", "agent 1", P2, 1.12, "billed", "c", "stopped when she cut to 10 prompts; 27 records unused", "agent 2's ledger, agent 1's split"); used.add("screen")
add(F, "screen: 10 prompts", "agent 1", P2, float(led["screen"]["watcher_spend_usd"]) - 1.12, "billed", "a", "Qwen's numbers in her SoRH #1/#2/#3/#5", "agent 2's ledger, agent 1's split")
L("realness_step2", F, "a", "r_student replies on her 10 (#1, #5)")
L("realness_cues", F, "a", "class-frame cells in her #1/#5 (+$0.2-0.8 in flight lost, not recorded)")
L("sorh_fill20", F, "a", "fills her cells to 20 prompts (k/20)")
F = "SoRH: thank-you / count-free versions (agent 1)"
for n in led:
    if led[n]["owner"] == A1 and n.startswith(("mean_letter_sorh", "thanks_once", "countfree_", "countfree2", "countfree450_embarr", "countfree450_judge", "countfree450_conflict", "countfree450_screen", "topup", "judgever", "conflict")):
        L(n, F, "a", "notes/sorh_thanks_table.md (verified, 236 replies)")
F = "SoRH: priority study (agent 1)"
L("countfree450_priority", F, "a", "notes/sorh_priority_results.md (verified)")
F = "SoRH: DeepSeek / GLM / 27B replications"
L("sorh_deepseek_bg", F, "a", "25 Oct quick check", usd=2.95 - 1.96)
add(F, "sorh_deepseek_bg: Sol reasoning labels", "agent 1", P2, 1.96, "billed", "c", "never used (reuse condition); replication drew fresh B/G", "agent 2's ledger, agent 1's split")
L("countfree450_deepseek20", F, "c", "SiliconFlow cut at 24k; superseded by the 64k run")
L("deepseek20_64k", F, "a", "DeepSeek column, four-model SoRH tables")
for n in ("len_check_glm52", "len_check_qwen27b"):
    L(n, F, "a", "length gate passed (method)")
L("glm52_20", F, "a", "GLM column (sorh_models20_results.md, verified)")
L("qwen27b_20", F, "a", "27B column (verified)")
for n in ("mean_letter_ds450", "mean_letter_ds0", "keyed_car_ds", "keyed_car_qwen"):
    L(n, F, "a", "rows in sorh_cues.md (verified)")
add(F, "GLM/27B mean-letter and keyed-car stages (27 Oct 11:14Z)", "agent 1", P2, 0.096 + 0.0017, "billed", "p", "just finished; not yet written up", "agent 2's messages (27 Oct)")
F = "SoRH: judges (hesitation, spiral, depth)"
L("hesitation_judge", F, "a", "sorh_hesitation_spiral_results.md (verified)")
L("spiral_judge", F, "a", "sorh_hesitation_spiral_results.md (verified)", usd=20.35)
L("depth_pilot", F, "b", "depth-v1 missed the support bar (validation)")
L("depth_dev", F, "b", "depth-v2 fresh check failed, preview separated nothing; full run dropped", owner="agent 10")
F = "Cooperation study (agent 10)"
L("coop_judges", F, "p", "SoRH coop-v1 labels; awaiting her spot check")
L("ib_coop_pass", F, "p", "IB coop-v1 labels; awaiting her spot check", owner="agent 11")

A3 = "Persistance in SoRH agent 3"
F = "SoRH: multi-turn screen and replications (agent 3)"
L("mt_screen", F, "a", "her #4 (cue 10); cues #9-#11")
F2 = "SoRH: coding-chat cue screen"
L("cue_screen_turn1", F2, "a", "code measures in verified notes")
L("cue_screen_step2", F2, "a", "code measures in verified notes (guard stop at 408/420, finished)")
L("cue_screen_judge", F2, "b", "judge failed its hand check (6/12), not used", usd=0.16)
L("mt_deepseek", F, "c", "provider cut (SiliconFlow hidden 24k); restarted at 64k")
for n, usd in (("mt_deepseek_64k", None), ("mt_glm52", None), ("mt_qwen27b", None),
               ("mt_nobody_qwen24t", 0.66), ("mt_nobody_deepseek", 0.71), ("mt_nobody_glm52", 0.64), ("mt_nobody_qwen27b", 0.38)):
    L(n, F, "a", "#4 four models / second experiment (verified)", usd=usd)

F = "IB: persistence and momentum (agent 4)"
L("agent4_run5", F, "c", "stopped by her (investigative, not quantitative); 19 of 22 finished episodes unused (pro rata)",
  usd=14.05 * 19 / 22)
add(F, "agent4_run5: the 3 episodes cited in §18 finding 3 (pro rata)", "agent 4", P2, 14.05 * 3 / 22, "est", "a",
    "§18 finding 3 (C_STOP 0/3)", "agent 2's ledger, split pro rata by agent 10 (verifier)")
L("agent4_file_probe", F, "b", "n=1 per file; no effect measurable")
L("agent4_file_probe_5tasks", F, "b", "no effect either way", usd=1.49)
add(F, "agent4_file_probe_5tasks: lost at the guard", "agent 4", P2, 1.60, "est", "c", "in-flight work lost at the guard", "agent 2's ledger, agent 4's split")
F = "IB: DeepSeek / GLM / 27B charts (§16-§22, agent 4)"
L("agent4_deepseek_check", F, "b", "quick check; go-ahead for §17")
for n in ("agent4_ds_stop", "agent4_ds_momentum_run", "agent4_ds_off_before", "agent4_stopdet_qwen", "agent4_stopdet_ds",
          "agent4_rep_glm_check", "agent4_rep_q27_check", "agent4_rep_q27_before", "agent4_rep_glm_after",
          "agent4_rep_glm_stopdet", "agent4_rep_q27_stopdet", "agent4_rep_q27_after", "agent4_rep_glm_before_fill",
          "agent4_rep_glm_before_fill_A_alive", "agent4_rep_q27_after_fill"):
    L(n, F, "a", "charts A-D / finding 3 (§17-§22)")
L("agent4_ds_detect_prefix", F, "b", "DeepSeek mostly undecided at that turn")
L("agent4_ds_resample", F, "b", "DeepSeek mostly undecided at that turn")
L("agent4_rep_glm_before", F, "a", "chart 1 (GLM)", usd=9.07 - 0.58)
add(F, "agent4_rep_glm_before: in flight at the $9 cap", "agent 4", P2, 0.58, "est", "c", "cap from an estimate GLM overran by ~20%", "agent 2's ledger, agent 4's split")
add(F, "stopdet and §21 judges", "agent 4", P2, 0.31 + 0.27, "billed", "a", "charts C/D", "logs/ib_persistence records")

F = "Realness probe (agent 5)"
for n in ("probe", "realness_candidates", "realness_step2_probe", "realness_step3_probe", "ds_probe_first", "ds_probe_switch",
          "agent5_a1_glm_early", "agent5_a1_q27_early", "agent5_glm_probe_first", "agent5_q27_probe_first",
          "agent5_glm_probe_switch", "agent5_q27_probe_switch", "agent5_nobody_qwen", "agent5_nobody_ds",
          "agent5_nobody_glm", "agent5_nobody_q27"):
    L(n, F, "a", "SoRH k/20 cells, realness frames, replications, #4 nobody arm")
L("test_4a_privacy", F, "b", "informative null (p 0.69)")
L("run5_check", F, "b", "gate failed (R 0/48 vs C 0/48)")
L("cue_gate", F, "b", "gate failed (10/60); screen run anyway")
L("cue_cells_probe", F, "b", "probe can't separate the cues")

F = "Transcript judges and labels (Goodfire + ours)"
add(F, "test_excuse Luna + Sol pilots", "agent 6", P2, 0.01 + 0.23, "billed", "b", "precision gate failed -> Sol fallback", "agent 6's reply"); used.add("agent6_test3")
add(F, "test_excuse Sol hybrid + Luna screen + recall", "agent 6", P2, 11.94, "billed", "a", "test 3 / map row 2v", "agent 6's reply")
add(F, "gf_catalogue momentum", "agent 6", P2, 0.12, "billed", "a", "map row 4a", "agent 6's reply")
L("agent7_q5c_judge", F, "a", "Goodfire 5(c): 'test of me' a reason to hold back ~83% (graphs Q5, her doc #4)")
L("agent7_ib_b_judge", F, "a", "capability-eval remarks mostly neutral (graphs Q5, her doc #4)")
F = "Dashboard"
L("agent6_dashboard_seed_ds", F, "b", "no gaming; honest exit", usd=2.19, basis="billed")
L("agent6_dashboard_seed_qwen", F, "b", "honest success; bar within reach -> harder-target run", usd=12.07, basis="billed")
L("agent6_dashboard_hard_qwen", F, "p", "running")

F = "IB: who reads the reply / forensics (agent 8)"
L("agent8_exp9_p1", F, "b", "no detectable effect (19/20, 19/20, 20/20), verified")
L("agent8_exp10", F, "a", "grading off after the 1st hack step: stopped the hack at all 10 discordant points (her IB write-up)")
L("agent8_exp11_b1", F, "c", "stopped by her at 5/60; no statistics")
F = "IB: persistence and momentum (agent 4)"
for n in led:
    if n.startswith("agent8_momentum"):
        L(n, "IB: momentum set and follow-ups (agents 8, 14, 15)", "b", "investigative, n=1 per variant, descriptive; use in her write-up untraced")
F = "HVTB"
L("hvtb_stage1", F, "c", "stopped for the battery; re-run as stage 1b", owner="agent 8")
for n in ("hvtb_stage1b", "hvtb_stage2", "hvtb_l3", "hvtb_l0", "hvtb_deepseek"):
    L(n, F, "b", "pilot + DeepSeek check (7/8 behaviour; DeepSeek ran solve.sh 3/8)", owner="agent 8")
L("hvtb_framing", F, "b", "sentence test null (14/37 vs 16/37, p 0.75)", owner="orchestrator")
add(F, "hvtb_framing gates", "orchestrator", P2, 0.23, "billed", "b", "both gates failed", "logs/hvtb_framing records")

F = "Other envs (our scenarios, D1, provenance, norvane)"
L("d1b_pilot", F, "b", "couldn't use: 80-message limit, false-positive hack flags; dropped by her", owner="orchestrator")
L("d1c_pilot", F, "c", "stopped 6 min in, no episode finished; dropped", owner="orchestrator")
add(F, "provenance pilot (agent 12)", "agent 12", P2, 0.10, "billed", "b", "comprehension gate failed; behaviour run skipped as registered", "agent 12's results note")
F = "Dark Mode"
L("darkmode_threeway", F, "c", "first launch stopped with 0 trajectories (in-flight lost)", owner="orchestrator")
L("darkmode_threeway_run3", F, "b", "informative null: 'noise' by the rule (fabricate R 0/10, C 0/10, G 1/9)", owner="orchestrator")
L("darkmode_threeway_run4", F, "b", "top-up of the same null", owner="orchestrator")
L("darkmode_threeway_run4_C_alive", F, "b", "", owner="orchestrator")
L("darkmode_ds_run", F, "c", "mostly broke on DeepSeek's tool-call format (harness); redone with a fix", owner="orchestrator")
L("darkmode_ds_fix", F, "b", "no fabrication; descriptive", owner="orchestrator")
L("darkmode_ds_fix_G_alive", F, "b", "", owner="orchestrator")
add(F, "realness gates (Qwen passed, DeepSeek failed)", "orchestrator", P2, 0.571 + 0.255, "billed", "b", "gates", "notes/darkmode_threeway.md")

F = "IB: persistence and momentum (agent 4)"
add("IB: momentum set and follow-ups (agents 8, 14, 15)", "ib_momentum_aisi pilot (agent 15)", "agent 15", P2, 1.57, "billed", "b", "screening pilot, n=1 per condition, descriptive", "agent 15's results note")
add("IB: momentum set and follow-ups (agents 8, 14, 15)", "ib_authority (agent 14)", "agent 14", P2, 0.52, "billed", "c", "technical failure: snapshot bug (v1), API errors (v2); no comparison", "agent 14's results note")

F = "IB: cue screens"
S = "agent 11's reply"
add(F, "LCB pilot (episodes + judges)", "agent 11", P2, 6.35, "billed", "b", "setup for a screen that ended as leads", S)
add(F, "IB-SWE pilot", "agent 11", P2, 3.30, "billed", "b", "setup", S)
add(F, "LCB screen (78 + completion)", "agent 11", P2, 66.60, "est", "b", "leads only; G cut 5/6 so disclosure NOT READABLE", S)
add(F, "LCB judges", "agent 11", P2, 21.50, "billed", "b", "leads only", S)
add(F, "IB-SWE screen", "agent 11", P2, 35.98, "est", "b", "leads only; no follow-up (her decision)", S)
add(F, "IB-SWE judges", "agent 11", P2, 10.43, "billed", "b", "leads only", S)
add(F, "support passes (calibration failed)", "agent 11", P2, 0.378, "billed", "b", "coder calibration failed (kappa 0.53), not used", S)
add(F, "support: DeepSeek attempt 2", "agent 11", P2, 0.043, "billed", "c", "malformed JSON from our json_object choice", S)
F = "SWE-V / DeepSWE"
add(F, "SWE-V pipeline check", "agent 11", P2, 1.17, "billed", "b", "setup (grading path bug re-graded at $0)", S)
add(F, "SWE-V screen (incl. URLError at 35 + completion)", "agent 11", P2, 18.94, "billed", "b", "informative null: 0/72 measurable hacks", S)
add(F, "SWE-V judges", "agent 11", P2, 7.92, "billed", "b", "informative null", S)
F = "IB: chat vs harness, homework, rejection (agent 11)"
for it, usd, cls, out in [
    ("chat Qwen 2.4T + completion", 4.42, "a", "verified, on her IB page"),
    ("chat DeepSeek (SiliconFlow 64k)", 4.01 - 0.72, "a", "verified; partly superseded by the Novita re-run"),
    ("chat DeepSeek: 5 length cuts", 0.72, "c", "provider / our length cuts"),
    ("chat GLM", 1.89 - 0.29, "a", "verified"),
    ("chat GLM: 1 cut at 131k", 0.29, "c", "length cut"),
    ("chat Qwen 27B DeepInfra stage 1", 0.0, "b", "gate failed (provider errors) -> provider switch"),
    ("chat Qwen 27B Parasail", 2.43, "a", "verified"),
    ("homework Qwen + re-draw", 0.77, "a", "verified so far"),
    ("homework DeepSeek SiliconFlow 64k", 0.64, "c", "superseded by her 'let it think as long as it needs'"),
    ("DeepSeek step 0 Novita", 0.08, "c", "uninformative: prompt design"),
    ("homework DeepSeek Novita", 0.92, "a", "verified so far"),
    ("homework GLM + re-draw", 0.81 - 0.275, "a", "verified so far"),
    ("homework GLM: cut at 131k", 0.275, "c", "length cut, re-drawn"),
    ("homework Qwen 27B + re-draw", 0.77, "a", "verified so far"),
    ("rejection Qwen + re-draw", 0.57, "a", "verified so far"),
    ("rejection DeepSeek", 0.68, "a", "verified so far"),
    ("rejection GLM + re-draws", 1.15 - 0.29, "a", "verified so far"),
    ("rejection GLM: cut at 131k", 0.29, "c", "length cut, re-drawn"),
    ("rejection Qwen 27B + re-draw", 1.09, "a", "verified so far"),
]:
    add(F, it, "agent 11", P2, usd, "billed", cls, out, S)
L("agent11_chat_dsn", F, "p", "running (DeepSeek chat re-run on Novita)")
for n in led:
    if led[n]["owner"].startswith("Impossiblebench dataset design agent 11"):
        used.add(n)  # replaced by agent 11's billed figures above
for n in ("ib_lcb_pilot", "ib_lcb_pilot_judges"):
    used.add(n)

F = "Realness probe (agent 5)"
add(F, "eval_probe ledger lines 25-26 Oct (probe_items*.jsonl)", "untraced", P2, 1.05, "billed", "u", "not agent 5's; owner untraced", "logs/eval_probe ledger; agent 5")

STOPPED = "stopped by a change of plan"
LIMIT = "superseded: design or limits fixed after a run"
INFLIGHT = "in-flight work lost at a pause, cap, guard or sleep"
PROVIDER = "provider cuts or harness-format failure"
BUG = "our bug"
UNUSED = "made but never used"
for it, c in {
    "agent4_run5": STOPPED, "agent8_exp11_b1": STOPPED, "screen: first launch, 20 prompts": STOPPED, "d1c_pilot": STOPPED,
    "homework DeepSeek SiliconFlow 64k": STOPPED,
    "stage1_false (50-message limit)": LIMIT, "stage1_person: false-reject arm at 50 messages": LIMIT,
    "graded/d1 C1-C4": LIMIT, "1g scale-up launch 1 (SIGINT)": LIMIT, "DeepSeek step 0 Novita": LIMIT,
    "labelling: stopped v3.3 sample run": LIMIT, "stakes rubric v1": LIMIT,
    "stage1_m100: lost in the pause": INFLIGHT, "darkmode_threeway": INFLIGHT, "agent4_file_probe_5tasks: lost at the guard": INFLIGHT,
    "run 1: in flight at the $20 cap": INFLIGHT, "step 3: partial logs / lost in the pause": INFLIGHT,
    "round1c lost at her 19:24 pause": INFLIGHT, "agent4_rep_glm_before: in flight at the $9 cap": INFLIGHT,
    "DeepSWE first runs stalled by sleep": INFLIGHT, "DeepSWE timed-out calls": INFLIGHT,
    "H_network first try (connection error at the pause)": INFLIGHT, "c5c6_rep/cancelled (restart for key floor)": INFLIGHT,
    "stage1/cancelled (relaunched 2 min later)": INFLIGHT, "graded/g3_ext_aborted": INFLIGHT, "hvtb_stage1": INFLIGHT,
    "darkmode_ds_run": PROVIDER, "countfree450_deepseek20": PROVIDER, "mt_deepseek": PROVIDER,
    "chat DeepSeek: 5 length cuts": PROVIDER, "chat GLM: 1 cut at 131k": PROVIDER, "rejection GLM: cut at 131k": PROVIDER,
    "homework GLM: cut at 131k": PROVIDER, "ib_authority (agent 14)": PROVIDER,
    "labelling: unquoted zsh variable sent a full-episode Sol run": BUG, "raw_excluded re-run; v3.3 partial": BUG,
    "support: DeepSeek attempt 2": BUG, "tau banking episode": BUG,
    "sorh_deepseek_bg: Sol reasoning labels": UNUSED, "logs/grader: labelling prototype": UNUSED,
    "smoke tests; tau first view dropped mid-run": STOPPED,
}.items():
    CAUSE[it] = c
for r in rows:
    if r["cls"] == "c":
        r["cause"] = CAUSE[r["item"]]
    else:
        assert r["item"] not in CAUSE, r["item"]

missing = [n for n in led if n not in used]
assert not missing, missing

if OUT:
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

# ---------------- tables ----------------
def usd(r, f13):
    return r["usd"] if (r["basis"] != "est" or f13) else r["usd"] / 1.3


for f13 in (True, False):
    tot = sum(usd(r, f13) for r in rows)
    by = defaultdict(float)
    for r in rows:
        by[r["cls"]] += usd(r, f13)
    print(f"\n== {'x1.3' if f13 else 'x1.0'} total ${tot:,.2f}  " + "  ".join(f"{k} ${v:,.2f} ({100*v/tot:.1f}%)" for k, v in sorted(by.items())))
bas = defaultdict(float)
for r in rows:
    bas[r["basis"]] += r["usd"]
print("by basis (x1.3):", {k: round(v, 2) for k, v in bas.items()})
per = defaultdict(float)
for r in rows:
    per[r["period"]] += r["usd"]
print("by period (x1.3):", {k: round(v, 2) for k, v in per.items()})

fam = defaultdict(lambda: defaultdict(float))
for r in rows:
    fam[r["family"]][r["cls"]] += usd(r, False)
    fam[r["family"]]["tot"] += r["usd"]
    fam[r["family"]]["tot10"] += usd(r, False)
print("\n| Family | $ best (x1.0) | $ at x1.3 (overstates) | a | b | c | p | u |")
print("|---|---|---|---|---|---|---|---|")
for k in sorted(fam, key=lambda k: -fam[k]["tot10"]):
    d = fam[k]
    print(f"| {k} | {d['tot10']:.2f} | {d['tot']:.2f} | " + " | ".join(f"{d[c]:.2f}" if d[c] else "–" for c in "abcpu") + " |")
cz = defaultdict(lambda: [0.0, 0.0])
for r in rows:
    if r["cls"] == "c":
        cz[r["cause"]][0] += r["usd"]; cz[r["cause"]][1] += usd(r, False)
print("\nwaste by cause (x1.3, x1.0):")
for k, v in sorted(cz.items(), key=lambda kv: -kv[1][0]):
    print(f"  {v[0]:7.2f} {v[1]:7.2f}  {k}")
own = defaultdict(lambda: defaultdict(float))
for r in rows:
    own[r["owner"]][r["period"]] += usd(r, False)
print("\nby owner, x1.0:", {k: (round(v["before"], 2), round(v["after"], 2)) for k, v in sorted(own.items())})
print("\nwaste rows (c), largest first:")
for r in sorted([r for r in rows if r["cls"] == "c"], key=lambda r: (r["cause"], -r["usd"])):
    print(f"| {r['item']} | {r['owner']} | {usd(r, False):.2f} | {r['usd']:.2f} | {r['basis']} | {r['cause']} | {r['outcome']} |")

print("\npending and untraced rows:")
for r in rows:
    if r["cls"] in "pu":
        print(f"| {r['item']} | {r['owner']} | {usd(r, False):.2f} | {r['basis']} | {r['cls']} | {r['outcome']} |")
big = sorted([r for r in rows if r["cls"] == "b"], key=lambda r: -usd(r, False))[:12]
print("\nlargest b rows (x1.0):")
for r in big:
    print(f"  {usd(r, False):7.2f} {r['owner']:10s} {r['family'][:38]:38s} {r['item']} -- {r['outcome']}")
