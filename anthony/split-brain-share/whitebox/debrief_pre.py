"""Pre-write probes: per run and condition, how many regenerated writes credit the source (debrief_code.credits: the
name with attribution wording) / name it at all, of the samples that wrote the file. python3 debrief_pre.py [--pool]"""
import json, sys
from collections import defaultdict
sys.path.insert(0, __import__("os").path.dirname(__file__))
import debrief_code as dc
CONDS = ["pre0", "pre", "pre_belief", "pre_belief_user", "pre_belief_asked", "pre_belief_reviewer", "pre_user_results", "pre_known", "pre_mind", "pre_draft", "pre_user", "pre_name", "pre_free", "pre_cost"]
g = defaultdict(lambda: [0, 0, 0, 0])
for r in dc.rows():
    if r["probe"] in CONDS:
        x = g[(r["run"], r["probe"])]
        x[0] += 1; x[1] += r["edited"]; x[2] += r["edit_names"] == 1; x[3] += r["edit_credits"] == 1
runs = sorted({k[0] for k in g}, key=lambda r: (dc.KIND[r], r))
print(f"{'run':24} {'kind':8} " + " ".join(f"{c:>9}" for c in CONDS) + "   credits|names/wrote")
for run in runs:
    print(f"{run:24} {dc.KIND[run]:8} " + " ".join(f"{(str(g[(run, c)][3]) + '|' + str(g[(run, c)][2]) + '/' + str(g[(run, c)][1])) if (run, c) in g else '-':>9}" for c in CONDS))
if "--pool" in sys.argv:
    for kind in ("lost", "decided"):
        tot = {c: [sum(g[(r, c)][j] for r in runs if dc.KIND[r] == kind) for j in (3, 2, 1)] for c in CONDS}
        print(f"{'POOLED':24} {kind:8} " + " ".join(f"{str(v[0]) + '|' + str(v[1]) + '/' + str(v[2]):>9}" for v in tot.values()))

# pre / pre_draft: the stated sentence (the reply's text before the write) names the source, and the file then does or not
said = defaultdict(lambda: [0, 0, 0])
for r in dc.rows():
    if r["probe"] in ("pre", "pre_belief", "pre_belief_user", "pre_belief_asked", "pre_belief_reviewer", "pre_user_results", "pre_draft") and r["edited"]:
        x = said[(dc.KIND[r["run"]], r["probe"])]
        x[0] += r["answer_names"]; x[1] += r["answer_names"] and r["edit_names"] == 1; x[2] += 1
for k, v in sorted(said.items()):
    print(f"{k[0]} {k[1]}: stated sentence names the source in {v[0]} of {v[2]} writes; the file names it in {v[1]} of those {v[0]}")
