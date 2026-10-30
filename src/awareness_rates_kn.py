"""Episode-level A/B/C rates as k/n, the rule of src/awareness_llm.py `rates`: an episode counts for a category if
any of its classified passages is labelled positive; episodes without candidates count as negative.

  python src/awareness_rates_kn.py logs/awareness_llm candidates_all_fill.jsonl labels_final_fill.jsonl <dir with dl/>

<dir with dl/> is any directory whose dl/ points at logs/data (awareness.define_sets reads dl/goodfire, dl/goodfire_swe,
dl/goodfire_other)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from awareness import define_sets  # noqa: E402

aw, cand_name, lab_name, data_parent = sys.argv[1:5]
labs = {json.loads(l)["id"]: json.loads(l) for l in open(Path(aw) / lab_name)}
pos = defaultdict(lambda: {"A": 0, "B": 0, "C": 0})
for l in open(Path(aw) / cand_name):
    r = json.loads(l)
    g = labs.get(r["id"])
    if g:
        e = pos[(r["bench"], r["model"], r["row"])]
        for c in "ABC":
            e[c] |= int(g[c])
totals = defaultdict(int)
for bench, model, path in define_sets(Path(data_parent)):
    with open(path) as fh:
        for line in fh:
            t = json.loads(line)["traces"][0]
            split = t["task"]["data"].get("split")
            key = f"{bench} ({'possible' if split == 'original' else 'impossible'})" if bench == "ImpossibleBench" else bench
            totals[(key, model)] += 1
print("| Benchmark | Model | n | A alignment eval | B capability eval | C previously seen |")
print("|---|---|---|---|---|---|")
for (bench, model), n in sorted(totals.items()):
    rows = [v for (b, m, _), v in pos.items() if b == bench and m == model]
    k = {c: sum(v[c] for v in rows) for c in "ABC"}
    print(f"| {bench} | {model} | {n} | " + " | ".join(f"{k[c]}/{n} ({100 * k[c] / n:.1f}%)" for c in "ABC") + " |")
