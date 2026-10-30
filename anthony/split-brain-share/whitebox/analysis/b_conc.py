# B: concept-set z (centred and plain, band L36-52) averaged over each site's tokens and each named moment, against a null of
# 2,000 random equal-length spans of the same run's subject tokens (percentile), plus the same over write (tool-call) tokens only
import json, numpy as np
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
BAND = [36, 40, 42, 44, 48, 52]
rng = np.random.default_rng(0)
for t in ["p04-r2-A0-q27b-tc-B63", "p03-beval-q27b-1-tc-B62", "p05-c1-A0-q27b-tc-B119", "p04-s0-A0-q27b-1-tc-B65", "p03-bnote-eval-q27b-1-tc-B127"]:
    d = CAPS / t; v = json.loads((d / 'view.json').read_text()); C = v['concepts']
    a = np.load(d / 'readers' / 'concepts.npy').astype(np.float32)
    mean, sd = np.array(C['mean']), np.array(C['sd'])
    z = (a - mean) / sd                                    # [n, L, S, M]
    li = [C['layers'].index(L) for L in BAND]
    zb = z[:, li].mean(1)                                  # [n, S, M]
    sets = C['sets']; ix = {p: i for i, p in enumerate(v['tokens']['pos'])}
    write = np.array([pt == 'c' for pt in v['tokens']['part']])
    def span_null(n, pool):
        starts = rng.integers(0, len(pool) - n, 2000)
        return np.stack([zb[pool[s:s + n]].mean(0) for s in starts])   # [2000, S, M]
    allidx = np.arange(len(zb)); widx = np.flatnonzero(write)
    print(f"\n######## {t}   (centred, band L36-52; value [percentile vs random spans of all subject tokens / of write tokens])")
    print(f"{'':26}" + "".join(f"{s:>22}" for s in sets))
    rows = [(f"site:{s['name']}", [ix[p] for p in s['pos'] if p in ix]) for s in v['sites']]
    rows += [(f"moment:{m['name']}", [ix[p] for p in range(*m['tokens']) if p in ix]) for m in v['moments'] if m['name'] != 'reply']
    for name, ids in rows:
        if not ids: continue
        n = len(ids); val = zb[ids].mean(0)
        nA, nW = span_null(n, allidx), span_null(n, widx)
        cells = []
        for si in range(len(sets)):
            x = val[si, 1]
            pa = (nA[:, si, 1] < x).mean() * 100; pw = (nW[:, si, 1] < x).mean() * 100
            flag = "*" if pa >= 97.5 or pw >= 97.5 else (" " if pa > 2.5 else "v")
            cells.append(f"{x:+6.2f} [{pa:3.0f}/{pw:3.0f}]{flag}")
        print(f"{name[:25]:26}" + "".join(f"{c:>22}" for c in cells) + f"  n={n}")
