# G: where in each write the history adds credit / prior-known content: per sentence of the write, the oracle lens's
# share of samples with that wording with full context vs with no history (strip), at the same tokens.
# python g_where.py [--L32|--L44] [--top N]
import json, re, collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
from f_dense import CRED, PRIOR  # noqa: E402  (same lexicons)
LAYER = next((int(a[3:]) for a in sys.argv if a.startswith("--L")), None)
TOP = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
rows = {}
for l in (CAPS / 'meta_dense.jsonl').open():
    try: r = json.loads(l); rows[(r['t'], r['pos'], r['reader'], r['layer'], r['src'])] = r
    except Exception: pass
full, strip = collections.defaultdict(list), collections.defaultdict(list)
for r in rows.values():
    if r['reader'] != 'olens' or (LAYER and r['layer'] != LAYER): continue
    if r['src'] == 'dense' and ':write' in r['tag']: full[(r['t'], r['pos'])] += r['texts']
    elif r['src'] == 'strip': strip[(r['t'], r['orig'])] += r['texts']
for t in sorted({k[0] for k in full}):
    v = json.loads((CAPS / t / 'view.json').read_text()); T = v['tokens']; ix = {p: i for i, p in enumerate(T['pos'])}
    ps = sorted(p for (tt, p) in full if tt == t)
    sents, cur = [], []
    for p in ps:  # sentences: split after a token ending in . ! ? or a newline
        cur.append(p)
        s = T['s'][ix[p]]
        if re.search(r"[.!?]\s*$|\n", s) and len(cur) >= 4: sents.append(cur); cur = []
    if cur: sents.append(cur)
    res = []
    for sp in sents:
        f = [x for p in sp for x in full[(t, p)]]; st = [x for p in sp for x in strip.get((t, p), [])]
        if not st: continue
        for name, rx in (("credit", CRED), ("prior", PRIOR)):
            a = sum(bool(rx.search(x)) for x in f) / len(f); b = sum(bool(rx.search(x)) for x in st) / len(st)
            res.append((a - b, name, a, b, ''.join(T['s'][ix[p]] for p in sp).strip()))
    print(f"\n######## {t}  ({len(sents)} sentences): largest full-context minus no-history differences")
    for name in ("credit", "prior"):
        for d, n, a, b, text in sorted([r for r in res if r[1] == name], reverse=True)[:TOP]:
            print(f"  {n:6} {a:.2f} vs {b:.2f} ({d:+.2f})  {text[:150]!r}")
