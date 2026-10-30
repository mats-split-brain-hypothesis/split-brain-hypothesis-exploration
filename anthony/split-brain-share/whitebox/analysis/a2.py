# at every site token (and the token after it): the written token's p, the top-3, and p of the 20th candidate (upper bound for anything absent)
import json, numpy as np
from pathlib import Path
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.8-27B", revision="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")
for t in ["p03-beval-q27b-1-tc-B62", "p04-s0-A0-q27b-1-tc-B65", "p05-c1-A0-q27b-tc-B119"]:
    d = CAPS / t; v = json.loads((d / 'view.json').read_text()); T = v['tokens']
    pidx = np.load(d / 'pred_idx.npy'); top = np.load(d / 'pred_topk_ids.npy'); lp = np.load(d / 'pred_topk_lp.npy')
    row = {int(p) + 1: i for i, p in enumerate(pidx)}; ix = {p: i for i, p in enumerate(T['pos'])}
    for s in v['sites']:
        print(f"\n{t[:22]} site {s['name']}: {s['phrase']!r}")
        ps = s['pos'] + [s['pos'][-1] + 1, s['pos'][-1] + 2]
        for p in ps:
            r = row.get(p); i = ix.get(p)
            if r is None or i is None: continue
            alts = ", ".join(f"{tok.decode([int(top[r, j])])!r} {np.exp(lp[r, j]):.2f}" for j in range(3))
            print(f"   {T['s'][i]!r:>16}  top: {alts}   p20={np.exp(lp[r, 19]):.4f}")
