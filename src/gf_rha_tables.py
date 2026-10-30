"""Render notes tables (markdown) from logs/rejection/gf_rha/{ib,other,q5a}.json. Counts only.
  python src/gf_rha_tables.py logs/rejection/gf_rha > <file>"""
import json, sys
from pathlib import Path
D = Path(sys.argv[1])
ib, ot, q5 = (json.loads((D / f).read_text()) for f in ("ib.json", "other.json", "q5a.json"))
M = ["Qwen", "GLM", "Kimi"]
def r(x): return "n/a" if x is None else ("inf" if x == float("inf") or x == "inf" else f"{x:.2f}" if x < 10 else f"{x:.1f}")
def ci(c): return "" if not c or c[0] is None else f" [{r(c[0])}, {r(c[1])}]"
def byrej(d): return " · ".join(f"{d[k][0]}/{d[k][1]}" for k in ("0", "1", "2", "3") if k in d)
def mh(m): return f"{r(m['rr'])}{ci(m['ci'])}; {m['informative_strata']} strata, {m['exposed_turns']} vs {m['unexposed_turns']} turns"
out = []
P = out.append
P("**Table 1. ImpossibleBench: first hack per turn, by rejections seen** (risk set: turns up to the episode's first flag "
  "of that status; impossible splits unless marked)\n")
P("| Model | Outcome | Episodes | 0 rejections · 1 · 2 · 3+ (first flags / turns at risk) | MH ratio, ≥1 vs 0, matched on turn | MH ratio, matched on characters so far |")
P("|---|---|---|---|---|---|")
for m in M:
    for o, on in (("hack_considered_any", "considered (first flag, any status)"), ("hack_attempted_enacted", "attempted or enacted")):
        for s, sn in (("impossible", "all"), ("impossible_rejected", "≥1 rejection")):
            q = ib[m]["Q1"][o][s]
            P(f"| {m} | {on}, {sn} | {q['episodes']} | {byrej(q['by_rej'])} | {mh(q['mh_turn'])} | {r(q['mh_chars']['rr'])}{ci(q['mh_chars']['ci'])}; {q['mh_chars']['informative_strata']} strata |")
P("\nPossible-split control (rejections are rare there):\n")
P("| Model | Outcome | Episodes (with ≥1 rejection) | 0 · 1 · 2 · 3+ |")
P("|---|---|---|---|")
for m in M:
    for o, on in (("hack_considered_any", "considered"), ("hack_attempted_enacted", "attempted or enacted")):
        q = ib[m]["Q1"][o]["possible"]
        P(f"| {m} | {on} | {q['episodes']} ({ib[m]['episodes']['possible_with_rejection']}) | {byrej(q['by_rej'])} |")
P("\n**Table 2. ImpossibleBench: first awareness remark per turn, by rejections seen**\n")
P("| Model | Remark (coverage) | Split | 0 · 1 · 2 · 3+ | MH ratio, matched on turn | MH ratio, characters |")
P("|---|---|---|---|---|---|")
for m in M:
    for o, on in (("first_A_complete", "A, complete"), ("first_B_complete", "B, complete"), ("first_A_sampled", "A, sampled"), ("first_B_sampled", "B, sampled")):
        for s in ("impossible", "possible"):
            q = ib[m]["Q2"][o].get(s)
            if not q: continue
            P(f"| {m} | {on} | {s} | {byrej(q['by_rej'])} | {mh(q['mh_turn'])} | {r(q['mh_chars']['rr'])}; {q['mh_chars']['informative_strata']} strata |")
P("\nRemarks per 10,000 characters of the model's text (impossible split, complete coverage), before any rejection vs after the first:\n")
P("| Model | A before | A after | B before | B after |")
P("|---|---|---|---|---|")
for m in M:
    a, b = ib[m]["Q2_rates"]["A_here"], ib[m]["Q2_rates"]["B_here"]
    P(f"| {m} | {a['before_any_rejection']['per_10k']} ({a['before_any_rejection']['passages']}) | {a['after_first_rejection']['per_10k']} ({a['after_first_rejection']['passages']}) | "
      f"{b['before_any_rejection']['per_10k']} ({b['before_any_rejection']['passages']}) | {b['after_first_rejection']['per_10k']} ({b['after_first_rejection']['passages']}) |")
P("\n**Table 3. ImpossibleBench: order of the first rejection (R), first A remark (A) and first hack flag (H)**\n")
P("| Model | Hack | Episodes with all three / impossible episodes | Orders (count) |")
P("|---|---|---|---|")
for m in M:
    for o, on in (("hack_considered_any", "considered"), ("hack_attempted_enacted", "attempted or enacted")):
        q = ib[m]["Q3"][o]
        P(f"| {m} | {on} | {q['n_with_all_three']}/{q['n_all']} | " + ", ".join(f"{k} {v}" for k, v in q["orders"].items()) + " |")
P("\n**Table 4. ImpossibleBench, rejected episodes: a turn with an A remark vs matched turns without** (strata: exact turn × rejections seen; turns before the first hack of that status; outcome: first hack in the next turns)\n")
P("| Model | Hack | Window | MH ratio | Informative strata | A turns (events) | Other turns (events) |")
P("|---|---|---|---|---|---|---|")
for m in M:
    for o, on in (("hack_considered_any", "considered"), ("hack_attempted_enacted", "attempted or enacted")):
        for w in ("t+1..t+2", "t+1", "t+1..t+5"):
            q = ib[m]["Q4"][o][w]
            P(f"| {m} | {on} | {w} | {r(q['rr'])}{ci(q['ci'])} | {q['informative_strata']} | {q['exposed_turns']} ({q['exposed_events']}) | {q['unexposed_turns']} ({q['unexposed_events']}) |")
P("\n**Table 5. SWE-bench Verified and DeepSWE: exposure = the model's own failing test run (no grader rejection exists)**\n")
P("| Bench | Model | Episodes (with own fail) | Outcome | 0 · 1 · 2 · 3+ own fails | MH, turn | MH, characters |")
P("|---|---|---|---|---|---|---|")
for b, bn in (("swev", "SWE-V"), ("deepswe", "DeepSWE")):
    for m in M:
        R = ot[b][m]
        for o, on in (("hack_considered_any", "first hack considered"), ("hack_attempted_enacted", "first hack attempted/enacted")):
            q = R["Q1"][o]["all"]
            P(f"| {bn} | {m} | {R['episodes']['n']} ({R['episodes']['with_own_fail']}) | {on} | {byrej(q['by_own_fail'])} | {mh(q['mh_turn'])} | {r(q['mh_chars']['rr'])}{ci(q['mh_chars']['ci'])} |")
        for o, on in (("first_B", "first B remark"), ("first_B_outside_flagged_turns", "first B, outside flagged turns")):
            q = R["Q2"][o]
            P(f"| {bn} | {m} | | {on} | {byrej(q['by_own_fail'])} | {mh(q['mh_turn'])} | {r(q['mh_chars']['rr'])} |")
P("\nSWE episode counts and awareness:\n")
P("| Bench | Model | Episodes | verdict_enacted yes | any flag | attempted/enacted flag | ≥1 test run | ≥1 own failing run | A remark | B remark | B per 10k chars before / after first own fail |")
P("|---|---|---|---|---|---|---|---|---|---|---|")
for b, bn in (("swev", "SWE-V"), ("deepswe", "DeepSWE")):
    for m in M:
        e = ot[b][m]["episodes"]; q = ot[b][m]["Q2_rates"]["B_here"]
        P(f"| {bn} | {m} | {e['n']} | {e['verdict_enacted_yes']} | {e['with_flag']} | {e['with_attempted_enacted_flag']} | {e['with_test_run']} | {e['with_own_fail']} | {e['with_A']} | {e['with_B']} | "
          f"{q['before_first_own_fail']['per_10k']} / {q['after_first_own_fail']['per_10k']} |")
P("\nOrder on SWE (F = first own failing run, B = first B remark, H = first hack):\n")
P("| Bench | Model | Hack | With all three / episodes | Orders |")
P("|---|---|---|---|---|")
for b, bn in (("swev", "SWE-V"), ("deepswe", "DeepSWE")):
    for m in M:
        for o, on in (("hack_considered_any", "considered"), ("hack_attempted_enacted", "attempted/enacted")):
            q = ot[b][m]["Q3"][o]
            P(f"| {bn} | {m} | {on} | {q['n_with_all_three']}/{q['n_all']} | " + ", ".join(f"{k} {v}" for k, v in list(q["orders"].items())[:4]) + " … |")
P("\nA B-remark turn vs matched turns without (exact turn × own fails seen; episodes with ≥1 own failing run; window t+1..t+2):\n")
P("| Bench | Model | Hack | MH | Strata | B turns (events) | Other (events) |")
P("|---|---|---|---|---|---|---|")
for b, bn in (("swev", "SWE-V"), ("deepswe", "DeepSWE")):
    for m in M:
        for o, on in (("hack_considered_any", "considered"), ("hack_attempted_enacted", "attempted/enacted")):
            q = ot[b][m]["Q4_B"][o]
            P(f"| {bn} | {m} | {on} | {r(q['rr'])}{ci(q['ci'])} | {q['informative_strata']} | {q['exposed_turns']} ({q['exposed_events']}) | {q['unexposed_turns']} ({q['unexposed_events']}) |")
P("\n**Table 6. τ3-bench and ShoppingBench (no rejection, no test runs): awareness and generic-monitor hack flags**\n")
P("| Bench | Model | Episodes | Turns | A remark (episodes) | B remark (episodes) | A / B per 10k chars | Monitor verdict yes / unclear / no |")
P("|---|---|---|---|---|---|---|---|")
for b, bn, key in (("tau3", "τ3", "τ3-bench"), ("shopping", "ShoppingBench", "ShoppingBench")):
    for m in ("GLM", "Kimi"):
        e = ot[b][m]["episodes"]; rt = ot[b][m]["rates_per_10k"]; mv = q5[f"{key} | {m} | monitor"]
        P(f"| {bn} | {m} | {e['n']} | {e['turns']} | {e['with_A']} | {e['with_B']} | {rt['A_here']['per_10k']} / {rt['B_here']['per_10k']} | {mv.get('yes',0)} / {mv.get('unclear',0)} / {mv.get('no',0)} |")
P("\n**Table 7. Awareness passages against Goodfire's own hack flags** (A on ImpossibleBench's impossible split, complete coverage; B on SWE, sampled coverage)\n")
P("| Bench | Model | Remark | Passages | In a turn with a hack flag | Text overlaps a flag's quote | … an attempted/enacted flag's |")
P("|---|---|---|---|---|---|---|")
for k, v in q5.items():
    if k.endswith("monitor"): continue
    b, m, kind = k.split(" | ")
    P(f"| {b} | {m} | {kind} | {v['passages']} | {v['in_flagged_turn']} | {v['overlap_flag_quote']} | {v['overlap_attempted_or_enacted_flag']} |")
P("\nEpisode-level hacks on ImpossibleBench's impossible splits (verdict_enacted v1.7 vs a visible pass):\n")
P("| Model | Impossible episodes | verdict_enacted yes | Visible pass | Pass without verdict_enacted | verdict_enacted without a pass | Episodes with ≥1 rejection |")
P("|---|---|---|---|---|---|---|")
for m in M:
    e = ib[m]["episodes"]
    P(f"| {m} | {e['impossible']} | {e['verdict_enacted_yes_impossible']} | {e['pass_impossible']} | {e['pass_but_not_enacted']} | {e['enacted_but_no_pass']} | {e['impossible_with_rejection']} |")
print("\n".join(out))
