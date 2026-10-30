"""Per-run table for the fictional-paper count: framing, segment, model, paper seen, flagged, outcome.
    python3 table.py          # counts
    python3 table.py --json   # the rows as JSON on stdout
"""
import json,re,csv,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
R=Path.home()/"split-brain-run/runs"
pos=set((HERE/"positives.txt").read_text().split())
border={l.split("\t")[0] for l in (HERE/"borderline.tsv").read_text().splitlines()[1:]}
codes={}
for r in csv.DictReader(open(Path.home()/"split-brain/pilots/tc-reading/codes.tsv"),delimiter="\t"): codes[r["run"]]=r
old={}
for l in open(Path.home()/"split-brain/pilots/persistence_outcomes.tsv"):
    if l.startswith("#") or l.startswith("run\t"): continue
    p=l.rstrip("\n").split("\t"); old[p[0]]=p[2] if len(p)>2 else ""
rows=[]
for d in sorted(R.iterdir()):
    f=d/"stream.jsonl"
    if not f.exists(): continue
    try: meta=json.load(open(d/"meta.json"))
    except: meta={}
    brief=(d/"brief.md").read_text() if (d/"brief.md").exists() else ""
    n=d.name; pilot=n.split("-")[0]
    if pilot=="p12": fr="p12 prompt"
    elif pilot=="p13": fr="p13 draft"
    elif "submit.py" in brief or "evaluation episode" in brief: fr="eval harness"
    else: fr="real repo / user"
    tc=bool(re.search(r"-tc[bc]?$",n))
    txt=f.read_text()
    readpaper=("raman2026" in txt) or ("white-bear-steering" in txt)
    nblocks=txt.count('"type":"thinking"')+txt.count('"type": "thinking"')
    out=codes.get(n,{}).get("outcome") or old.get(n,"")
    m=meta.get("model","").split("/")[-1]
    rows.append(dict(run=n,pilot=pilot,framing=fr,tc=tc,model=m,paper_seen=readpaper,fake=n in pos,border=n in border,outcome=out))
if "--json" in sys.argv:
    print(json.dumps(rows)); sys.exit()
from collections import Counter
def summ(sel,label):
    s=[r for r in rows if sel(r)]
    print(f"{label}: runs {len(s)}, paper seen {sum(r['paper_seen'] for r in s)}, fake-mention {sum(r['fake'] for r in s)}, borderline {sum(r['border'] for r in s)}")
summ(lambda r:True,"ALL")
summ(lambda r:r['tc'],"TC only")
summ(lambda r:not r['tc'],"old segment")
print("missing in table:", pos-{r['run'] for r in rows})
for k in ["framing","model"]:
    print("\nTC by",k)
    for v in sorted({r[k] for r in rows if r['tc']}):
        s=[r for r in rows if r['tc'] and r[k]==v and r['paper_seen']]
        print(f"  {v:20s} {sum(r['fake'] for r in s)}/{len(s)}")
    print("old by",k)
    for v in sorted({r[k] for r in rows if not r['tc']}):
        s=[r for r in rows if not r['tc'] and r[k]==v and r['paper_seen']]
        print(f"  {v:20s} {sum(r['fake'] for r in s)}/{len(s)}")
