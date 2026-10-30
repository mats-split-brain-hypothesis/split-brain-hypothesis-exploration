import json, re, collections
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
CRED = re.compile(r"credit|honest|诚实|cite|citation|acknowledg|attribut|original (author|discoverer|inventor)|named after its inventor|if you must|not new|re-validated|replicat", re.I)
rows = {}
for l in (CAPS / 'meta.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
R = [r for r in rows.values() if r['src'] == '3.8']
g = collections.defaultdict(list)
for r in R:
    k = r['tag'] if r['tag'].startswith('site') else ('plan' if r['tag'].startswith('plan') else 'random')
    run = r['t'][:24] if k != 'random' else 'ALL'
    g[(run, k, r['reader'] + str(r['layer'] or ''))] += r['texts']
print("credit / honesty / attribution wording, share of descriptions: olens32 olens44 olens56 nla42 | text-only")
for key in sorted({(a, b) for a, b, _ in g}, key=lambda k: (k[0] != 'ALL', k)):
    vals = []
    for rd in ("olens32", "olens44", "olens56", "nla42", "text-only"):
        xs = g.get((key[0], key[1], rd), [])
        vals.append(f"{sum(bool(CRED.search(x)) for x in xs) / len(xs):.2f}" if xs else "  - ")
    print(f"  {key[0]:24} {key[1][:24]:24} " + "  ".join(vals[:4]) + "  | " + vals[4])
