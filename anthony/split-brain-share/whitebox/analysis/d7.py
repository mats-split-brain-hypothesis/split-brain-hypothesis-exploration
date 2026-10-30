import json, re
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
NOTNOVEL = re.compile(r"not (a |very |particularly )?nov|not new|not original|no novelty|not a novelty|nothing new|standard|established practice|not (our|my) (own )?(invention|idea)|do(es)? not claim|reproduc|replicat|well.known|\bknown\b|classic|established|existing|borrow|prior|previous", re.I)
rows = {}
for l in (CAPS / 'meta.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
for site in ("site:opening", "site:safety-net-opening"):
    R = [r for r in rows.values() if r['t'].startswith('p05-c1') and r['tag'] == site and r['src'] == '3.8' and r['reader'] == 'olens']
    n = sum(len(r['texts']) for r in R); hits = [(r['pos'], r['layer'], x) for r in R for x in r['texts'] if NOTNOVEL.search(x)]
    print(f"\n== c1-A0 {site}: {len(hits)} of {n} oracle-lens samples with prior / not-novel wording")
    for p, L, x in hits[:14]:
        m = NOTNOVEL.search(x); print(f"  pos {p} L{L}: ...{x[max(0, m.start() - 110): m.end() + 70]!r}")
