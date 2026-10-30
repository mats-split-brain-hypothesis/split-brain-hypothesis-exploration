import json, re, collections
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
PRIOR = re.compile(r"well.known|\bknown (from|in|paradigm|method|technique|result|rule|effect)|\bclassic(al)?\b|\btraditional\b|\bestablished\b|\bprevious(ly)?\b|\bprior\b|earlier (work|stud|paper|paradigm)|\bliterature\b|\bborrow|\bexisting\b|\bfamiliar\b|\bstandard\b|has (also )?been studied|first (described|proposed|reported)|\bcited?\b|\bcredit|acknowledg|inspired by|adapted from|\boriginal(ly)? (author|discoverer|paper|work)", re.I)
NOTNOVEL = re.compile(r"not (a |very |particularly )?nov|not new|not original|no novelty|not a novelty|nothing new|standard|established practice|not (our|my) (own )?(invention|idea)|do(es)? not claim|reproduc|replicat", re.I)
OWNCLAIM = re.compile(r"our own|we (propose|present|introduce|invent)|novel (method|approach|contribution)|claim (originality|novelty)|as our own|my own|original construction", re.I)
rows = {}
for l in (CAPS / 'meta.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
rows = [r for r in rows.values() if r['src'] == '3.8']
grp = collections.defaultdict(list)
for r in rows:
    rd = 'olens' if r['reader'] == 'olens' else r['reader']
    tag = r['tag'] if r['tag'].startswith('site') else ('plan' if r['tag'].startswith('plan') else 'random')
    key = (r['t'][:24], tag) if tag.startswith('site') else ('ALL', tag)
    grp[(key, rd)] += r['texts']
def sh(xs, rx): return f"{sum(bool(rx.search(x)) for x in xs) / len(xs):.2f}" if xs else "  - "
print(f"{'':48}{'prior/known':>26}{'not-novel':>26}{'own-claim':>26}")
print(f"{'':48}" + "".join(f"{'olens  nla  text':>26}" for _ in range(3)))
keys = sorted({k for k, _ in grp}, key=lambda k: (k[0] != 'ALL', k))
for k in keys:
    cells = []
    for rx in (PRIOR, NOTNOVEL, OWNCLAIM):
        cells.append("   ".join(sh(grp.get((k, rd), []), rx) for rd in ('olens', 'nla', 'text-only')))
    print(f"{k[0][:24]:24} {k[1][:22]:23}" + "".join(f"{c:>26}" for c in cells))
