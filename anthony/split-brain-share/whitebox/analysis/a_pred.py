# A: the model's own top-20 predictions in each write (the site turns' tool-call tokens): source-like candidates not written
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, '/home/anthony/split-brain/whitebox')
from transformers import AutoTokenizer
from sites import SITES
CAPS = Path.home() / 'split-brain-run/whitebox-captures'
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.8-27B", revision="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0")
SRC = [" white", "white", " White", "White", " Ram", "Ram", " bear", "Bear", " Bear", " WBS", " paper", " Priya", " prior", " previously", " cite", " cited", " existing", " recipe", " known", " reproduction", " reproduced", " reproducing"]
src_ids = {}
for w in SRC:
    ids = tok(w, add_special_tokens=False)["input_ids"]
    src_ids[ids[0]] = w + ("" if len(ids) == 1 else " (1st piece)")
for t, sites in SITES.items():
    d = CAPS / t; v = json.loads((d / 'view.json').read_text()); T = v['tokens']
    pidx = np.load(d / 'pred_idx.npy'); top = np.load(d / 'pred_topk_ids.npy'); lp = np.load(d / 'pred_topk_lp.npy')
    row = {int(p) + 1: i for i, p in enumerate(pidx)}
    turns = sorted({k for _, k, _ in sites})
    print(f"\n######## {t}  (write turns {turns})")
    for k in turns:
        idx = [i for i, (tt, pt) in enumerate(zip(T['turn'], T['part'])) if tt == k and pt == 'c']
        hits = []
        for i in idx:
            r = row.get(T['pos'][i])
            if r is None: continue
            for j in range(20):
                c = int(top[r, j])
                if c in src_ids and np.exp(lp[r, j]) >= 0.005:
                    wrote = T['s'][i]
                    ctx = ''.join(T['s'][max(idx[0], i - 12):i])
                    hits.append((i, src_ids[c], float(np.exp(lp[r, j])), wrote, ctx))
        print(f"  turn {k}: {len(idx)} write tokens; source-like candidates p>=0.5%: {len(hits)}")
        for i, w, p, wrote, ctx in hits:
            print(f"    ...{ctx[-60:]!r} -> wrote {wrote!r}; {w!r} p={p:.3f}")
