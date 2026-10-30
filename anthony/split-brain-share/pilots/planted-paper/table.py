"""Per-run table for the planted-paper study (tc runs that saw the WBS paper).
    python3 table.py            # counts by framing / model / kind, overlap with fictional, outcomes
    python3 table.py --write    # also writes runs.tsv
Inputs: read_codes.tsv (hand codes per block), ../fictional-paper/table.py rows, ../tc-reading/codes.tsv."""
import csv, json, subprocess, sys, re
from pathlib import Path
from collections import Counter, defaultdict
HERE = Path(__file__).resolve().parent
rows = json.loads(subprocess.run([sys.executable, str(HERE.parent/"fictional-paper/table.py"), "--json"], capture_output=True, text=True).stdout)
rows = [r for r in rows if r["tc"] and r["paper_seen"]]
codes = {r["run"]: r for r in csv.DictReader(open(HERE.parent/"tc-reading/codes.tsv"), delimiter="\t")}
nblk = {}
for r in csv.reader(open(HERE/"hits.tsv"), delimiter="\t", quoting=csv.QUOTE_NONE): nblk.setdefault(r[0], None)
blocks = defaultdict(list)
for r in csv.reader(open(HERE/"read_codes.tsv"), delimiter="\t", quoting=csv.QUOTE_NONE):
    if r[0] == "run": continue
    blocks[r[0]].append(dict(block=int(r[1]), strength=r[2], kind=r[3], note=r[4]))
def nblocks(run):
    n = 0
    for l in open(Path.home()/f"split-brain-run/runs/{run}/stream.jsonl"):
        try: e = json.loads(l)
        except Exception: continue
        if e.get("type") == "assistant":
            n += sum(1 for c in e["message"].get("content", []) if isinstance(c, dict) and c.get("type") in ("thinking", "text"))
    return n
STRICT = {"misattributed", "uncredited"}
out = []
for r in rows:
    b = sorted(blocks.get(r["run"], []), key=lambda x: x["block"])
    strong = [x for x in b if x["strength"] == "s"]
    n = nblocks(r["run"]) if b else 0
    kinds = []
    for x in b:
        if x["kind"] not in kinds: kinds.append(x["kind"])
    out.append(dict(run=r["run"], framing=r["framing"], model=r["model"], outcome=codes.get(r["run"], {}).get("outcome", r["outcome"]),
        planted="strong" if strong else ("weak" if b else "no"), fictional=r["fake"],
        kinds=";".join(kinds), first_at=f"{b[0]['block']/max(n-1,1):.0%}" if b else "",
        judge_knows=any("judge knows" in x["note"] or "owner knows" in x["note"] for x in b),
        design=codes.get(r["run"], {}).get("design", ""), first_quote=(strong or b or [{"note": ""}])[0]["note"]))
if "--write" in sys.argv:
    with open(HERE/"runs.tsv", "w") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t", lineterminator="\n"); w.writeheader(); w.writerows(out)
def rate(s): 
    c = [x for x in s if x["outcome"] and x["outcome"] not in ("cutoff", "?", "")]
    return f"{sum(x['outcome'] in STRICT for x in c)}/{len(c)}"
print("framing | runs | strong | weak | cheat strong | cheat weak | cheat none")
for fr in ["eval harness", "real repo / user", "p12 prompt", "p13 draft"]:
    s = [x for x in out if x["framing"] == fr]
    g = lambda k: [x for x in s if x["planted"] == k]
    print(f"{fr} | {len(s)} | {len(g('strong'))} | {len(g('weak'))} | {rate(g('strong'))} | {rate(g('weak'))} | {rate(g('no'))}")
print("\nby model (strong / weak / all):")
for m in sorted({x["model"] for x in out}):
    s = [x for x in out if x["model"] == m]
    print(f"  {m}: {sum(x['planted']=='strong' for x in s)} / {sum(x['planted']=='weak' for x in s)} / {len(s)}")
print("\nkinds (runs with each, strong runs, eval harness):", Counter(k for x in out if x["planted"]=="strong" and x["framing"]=="eval harness" for k in x["kinds"].split(";")))
print("kinds (strong runs, other framings):", Counter(k for x in out if x["planted"]=="strong" and x["framing"]!="eval harness" for k in x["kinds"].split(";")))
print("\noverlap with fictional (all framings): ")
for p in ["strong", "weak", "no"]:
    s = [x for x in out if x["planted"] == p]
    print(f"  planted {p}: fictional {sum(x['fictional'] for x in s)} / {len(s)}")
print("\ncheat by kind (eval harness, strong runs containing the kind):")
for k in ["trap", "boundary", "hint", "decoy", "open"]:
    s = [x for x in out if x["planted"]=="strong" and x["framing"]=="eval harness" and k in x["kinds"].split(";")]
    print(f"  {k}: {rate(s)}")
print("judge-knows (eval harness strong):", rate([x for x in out if x['planted']=='strong' and x['framing']=='eval harness' and x['judge_knows']]))
