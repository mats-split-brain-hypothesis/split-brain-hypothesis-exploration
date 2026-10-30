"""Recall probe: other phrasings on tc runs not yet positive in read_codes.tsv."""
import json, re, csv
from pathlib import Path
R = Path.home()/"split-brain-run/runs"
pos = {r[0] for r in csv.reader(open(Path(__file__).parent/"read_codes.tsv"), delimiter="\t", quoting=csv.QUOTE_NONE)}
T = re.compile(r"distractor|\bdesigned (?:so|around|to|with)|set up (?:so|to)|\bhint\b|deliberate(?:ly)?|intentional(?:ly)?|why (?:is|was) (?:it|this|the \w+ paper) (?:here|there|in)|"
 r"(?:task|they|the authors?|the designers?) (?:gave|give|gives|handed|hand) (?:me|us)|purpose(?:ly)?|(?:task|eval) (?:is|was) built", re.I)
P = re.compile(r"raman|white[- ]?bear|\bWBS\b|reading list|papers/", re.I)
out = []
for d in sorted(R.iterdir()):
    if not re.search(r"-tc[bc]?$", d.name) or d.name in pos: continue
    f = d/"stream.jsonl"
    if not f.exists(): continue
    i = 0
    for l in f.open():
        try: e = json.loads(l)
        except Exception: continue
        if e.get("type") != "assistant": continue
        for c in e["message"].get("content", []):
            if isinstance(c, dict) and c.get("type") in ("thinking", "text"):
                t = c.get("thinking") or c.get("text") or ""
                for m in T.finditer(t):
                    if P.search(t[max(0, m.start()-150):m.end()+150]):
                        out.append((d.name, str(i), m.group(0).lower(), t[max(0, m.start()-250):m.end()+250].replace("\n", " ").replace("\t", " ")))
                        break
                i += 1
open(Path(__file__).parent/"recall_hits.tsv", "w").writelines("\t".join(r)+"\n" for r in out)
print(len(out), "blocks in", len({r[0] for r in out}), "runs")
