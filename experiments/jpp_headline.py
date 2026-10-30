"""Headline bars for the J++ finalists page: plain J-lens, plain J++, the J-lens with S20x refitted on J++'s fit
split (supervised), the J-lens with S14b-knnxs8 on our fit pool plus J++'s fit cells (label-free) and the J-lens
with x13's blind glossary centre (glosb:desc: texts the model wrote from one README sentence), each with a 95 % bootstrap interval (items resampled within eval, 2000 draws), as the J++ paper's Figure 1.

    python experiments/jpp_headline.py

Reads ``out/analysis/jpp-finalists/{ranks.pt,ranks-pool-jpp.pt}`` (experiments/jpp_finalists.py) and
``umot/out/jpp/items.json`` (held-out split); writes ``out/analysis/jpp-finalists/headline.json``. Torch only here, so
the dashboard reads plain JSON.
"""

import json
from collections import defaultdict

import numpy as np
import torch

from jlm import OUT, REPO_ROOT

ROOT = OUT / "analysis" / "jpp-finalists"
ARMS = {"jlens": ("jlens", "zero"), "jpp": ("jpp", "zero"), "jlens+s20x-jpp": ("jlens", "s20x-jpp"),
        "jlens+s14b-knnxs8u": ("jlens", "S14b-knnxs8∪"), "jlens+glosb": ("jlens", "glosb:desc")}
EVALS = ["multihop", "multilingual", "typo", "association", "poetry"]
DRAWS, SEED = 2000, 0


def main() -> None:
    base = torch.load(ROOT / "ranks.pt", weights_only=False)
    pool = torch.load(ROOT / "ranks-pool-jpp.pt", weights_only=False)
    pairs = base["pairs"]
    split = {(m["eval"], m["item"]): m["split"] for m in json.loads((REPO_ROOT / "umot/out/jpp/items.json").read_text())}
    held = [k for k, (e, it, _) in enumerate(pairs) if split[e, it] == "held"]
    items = defaultdict(lambda: defaultdict(list))  # eval -> item -> pair indices (held-out only)
    for k in held:
        e, it, _ = pairs[k]
        items[e][it].append(k)
    rng = np.random.default_rng(SEED)
    draws = {e: [rng.integers(0, len(items[e]), len(items[e])) for _ in range(DRAWS)] for e in EVALS}
    out = {}
    for ro in ("rms", "cos"):
        for name, (lens, arm) in ARMS.items():
            key = f"{lens}|{arm}|{ro}|grid11"
            r = (base if key in base else pool)[key]
            hit = (r.min(1).values <= 10).float().numpy()
            per = {e: np.array([hit[ks].mean() for ks in items[e].values()]) for e in EVALS}
            cnt = {e: np.array([len(ks) for ks in items[e].values()]) for e in EVALS}
            # recall over pairs = pair-weighted mean of item means; each draw resamples items within eval
            point = {e: float((per[e] * cnt[e]).sum() / cnt[e].sum()) for e in EVALS}
            boot = {e: np.array([(per[e][d] * cnt[e][d]).sum() / cnt[e][d].sum() for d in draws[e]]) for e in EVALS}
            res = {}
            for mk, evs in (("macro", EVALS), ("macro4", EVALS[:4])):
                b = np.mean([boot[e] for e in evs], 0)
                res[mk] = [float(np.mean([point[e] for e in evs])), float(np.quantile(b, 0.025)), float(np.quantile(b, 0.975))]
            res |= {e: [point[e], float(np.quantile(boot[e], 0.025)), float(np.quantile(boot[e], 0.975))] for e in EVALS}
            out[f"{name}|{ro}"] = res
    (ROOT / "headline.json").write_text(json.dumps({"draws": DRAWS, "seed": SEED, "layers": "grid11", "scores": out}, indent=1))
    for k, v in out.items():
        print(k, [round(x, 3) for x in v["macro"]])


if __name__ == "__main__":
    main()
