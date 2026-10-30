# C: the paper's name in the J-lens top-10 (centred and plain, L32-60): rate per region, and where it surfaces with no name in the
# 30 tokens before (so it is not the lens reading the text)
import json, re, numpy as np
from pathlib import Path
from transformers import AutoTokenizer
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.8-27B", revision="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")
NAME_W = [" white", "white", " White", "White", "-white", " bear", "bear", " Bear", "Bear", "-bear", " Raman", " Ram", "Ram", "aman", " WBS", "WBS", " Priya", " Pri"]
name_ids = {tok(w, add_special_tokens=False)["input_ids"][0]: w for w in NAME_W}
name_ids = {i: w for i, w in name_ids.items() if tok.decode([i]).strip().lower() in {"white", "bear", "ram", "aman", "raman", "wbs", "w", "priya", "pri", "-white", "-bear"}}
print("name token ids:", {tok.decode([i]): i for i in name_ids})
TEXT = re.compile(r"white|bear|raman|wbs|priya", re.I)
for t in ["p04-r2-A0-q27b-tc-B63", "p03-beval-q27b-1-tc-B62", "p05-c1-A0-q27b-tc-B119", "p04-s0-A0-q27b-1-tc-B65", "p03-bnote-eval-q27b-1-tc-B127"]:
    d = CAPS / t; v = json.loads((d / 'view.json').read_text()); T = v['tokens']
    L = json.loads((d / 'readers' / 'jlens_meta.json').read_text())['layers']
    li = [L.index(x) for x in (32, 36, 40, 42, 44, 48, 52, 56, 60)]
    res = {}
    for m in ("centred", "plain"):
        ids = np.load(d / 'readers' / f'jlens_{m}_ids.npy')[:, li, :]
        res[m] = np.isin(ids, list(name_ids)).any(axis=(1, 2))
    s = T['s']; n = len(s)
    cat = "".join(s)
    starts = np.cumsum([0] + [len(x) for x in s])
    near = np.array([bool(TEXT.search(cat[starts[max(0, i - 30)]:starts[i + 1]])) for i in range(n)])
    part = np.array(T['part']); turn = np.array(T['turn'])
    from sites import SITES
    wturns = sorted({k for _, k, _ in SITES[t]})
    print(f"\n######## {t}")
    for m in ("centred", "plain"):
        r = res[m]
        print(f"  {m:8} name in top-10: all tokens {r.mean():.3f} (text has name nearby: {r[near].mean():.3f}, no name nearby: {r[~near].mean():.3f})")
        for k in wturns:
            w = (turn == k) & (part == 'c')
            print(f"     write turn {k}: {r[w].mean():.3f} of {w.sum()} tokens; with no name nearby {r[w & ~near].mean() if (w & ~near).any() else float('nan'):.3f} ({(w & ~near).sum()} tokens)")
    # instances in the writes with no name nearby (centred)
    r = res["centred"]; ids = np.load(d / 'readers' / 'jlens_centred_ids.npy')
    shown = 0
    for k in wturns:
        for i in np.flatnonzero((turn == k) & (part == 'c') & ~near & r):
            hitL = [L[j] for j in range(len(L)) if np.isin(ids[i, j], list(name_ids)).any()]
            words = sorted({tok.decode([int(x)]) for j in range(len(L)) for x in ids[i, j] if int(x) in name_ids})
            print(f"     turn {k} ...{''.join(s[max(0, i - 10):i])!r} [{s[i]!r}]  {words} at L{hitL}")
            shown += 1
            if shown > 25: break
