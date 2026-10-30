import json, re, collections, sys
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
STRICT = re.compile(r"white.?bear|\braman\b|\bwbs\b|prior (work|method|art|approach)|existing (method|work|approach|technique|recipe|paper)|previous(ly)? (work|paper|method|published|reported)|\bcit(e|es|ed|ing|ation)s?\b|\bcredit|attribut|plagiar|reproduc|replicat|borrow", re.I)
NAME = re.compile(r"white.?bear|\braman\b|\bwbs\b", re.I)
rows = {}
for l in (CAPS / 'meta.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
rows = list(rows.values())
agg = collections.defaultdict(lambda: [0, 0, 0])
for r in rows:
    if r['src'] != '3.8': continue
    rd = r['reader'] + (f"-L{r['layer']}" if r['layer'] else "")
    k = "site" if r['tag'].startswith("site") else ("plan" if r['tag'].startswith("plan") else "random")
    for x in r['texts']:
        a = agg[(rd, k)]; a[0] += bool(STRICT.search(x)); a[1] += bool(NAME.search(x)); a[2] += 1
print("strict source theme / the name itself, share of descriptions (site / plan / random)")
for rd in ["olens-L32", "olens-L44", "olens-L56", "nla-L42", "text-only"]:
    print(f"  {rd:10} " + "   ".join(f"{agg[(rd,k)][0]/agg[(rd,k)][2]:.3f}/{agg[(rd,k)][1]/agg[(rd,k)][2]:.3f}" for k in ("site", "plan", "random")))
# where the name itself appears in a reader's description: list them all (with the text-only at the same token)
print("\nevery description naming the source (white-bear / Raman / WBS), by run and position:")
tx = {(r['t'], r['pos']): r['texts'][0] for r in rows if r['reader'] == 'text-only'}
v = {}
for r in sorted(rows, key=lambda r: (r['t'], r['pos'])):
    if r['src'] != '3.8' or r['reader'] == 'text-only': continue
    for x in r['texts']:
        m = NAME.search(x)
        if m:
            if r['t'] not in v: v[r['t']] = json.loads((CAPS / r['t'] / 'view.json').read_text())
            T = v[r['t']]['tokens']; i = T['pos'].index(r['pos'])
            ctx = ''.join(T['s'][max(0, i - 8):i + 1])
            tn = bool(NAME.search(tx.get((r['t'], r['pos']), '')))
            print(f"  {r['t'][:22]} {r['tag'][:26]:26} {r['reader']}{r['layer'] or ''} ...{ctx[-40:]!r}  text-only names it: {tn}\n      {x[max(0, m.start() - 120): m.end() + 100]!r}")
