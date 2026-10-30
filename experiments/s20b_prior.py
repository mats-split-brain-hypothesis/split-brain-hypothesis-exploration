"""S20b readout-frequency prior (card S20b in mu-log; studies/S20.md insight 4): demote what the family-mean readout
surfaces in every family's cells, an IDF of the readout, pulled back into the residual stream. No targets.

For each layer L and family G, ``f_G[t]`` = the share of G's fit read cells whose top-K under ``J_L(h - mu_G)`` (cos)
holds token t (``mu_G`` = G's fit mean). For a read family F, ``c_F = log(eps + mean_{G != F} f_G)`` (other families
only: F's own cells never shape its prior), rescaled to [0, 1] and multiplied by ``s_L`` = the mean gap between the
1st and the K-th score of the fam readout at L, so beta = 1 can demote a token in every cell's top K by about that gap.
``g_{F,L}`` = the cos-readout pullback of ``c_F`` (``jlm.pullback``). The centre ``s20b:<K>:<beta>`` reads
``h - mu_fam - beta g_{F,L}``; the key ``all`` (every family pooled) is the prior for banks outside the 11.

  python experiments/s20b_prior.py --k 50 --device cuda      # -> out/priors/S20b/readfreq-k50.pt (+ .md decode)
"""

import argparse
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jlm import OUT, banks, capture
from jlm.lens import Lens
from jlm.mu import clusters
from jlm.pullback import Geometry

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]
EPS = 1e-3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=50)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--layers", default="grid")
    args = ap.parse_args()
    layers = GRID if args.layers == "grid" else [int(x) for x in args.layers.split(",")]
    t0 = time.time()
    lens = Lens(layers, args.device)
    geo = Geometry(lens)
    states = {}
    for f in clusters.FAMILIES:
        items = capture.load(banks.load(f, "fit"))
        states[f] = {L: torch.stack([it.acts[L][i].float() for it in items for i in range(len(it.positions))]) for L in layers}
    print(f"states loaded ({time.time() - t0:.0f}s)", flush=True)
    out = {"meta": {"k": args.k, "eps": EPS, "readout": "cos", "note": "no targets; family F's prior from other families"},
           "layers": {}, "decode": {}}
    md = [f"# S20b readout-frequency prior (K = {args.k}): the most demoted tokens per layer (pooled 'all' prior)", ""]
    for L in layers:
        t = time.time()
        freq, gaps = {}, []
        for f, S in states.items():
            X = S[L] - S[L].mean(0)
            cnt = torch.zeros(lens.vocab)
            for a in range(0, len(X), 256):
                sc = lens.scores(X[a : a + 256], L, "cos")
                top = sc.topk(args.k, dim=1)
                gaps.append((top.values[:, 0] - top.values[:, -1]).cpu())
                cnt += torch.bincount(top.indices.cpu().flatten(), minlength=lens.vocab).float()
            freq[f] = cnt / len(X)
        s_L = torch.cat(gaps).mean().item()
        lo, hi = torch.log(torch.tensor(EPS)), torch.log(torch.tensor(1 + EPS))
        C, keys = [], []
        for key in list(states) + ["all"]:
            others = [freq[g] for g in states if g != key]
            c = (torch.log(EPS + torch.stack(others).mean(0)) - lo) / (hi - lo) * s_L
            C.append(c)
            keys.append(key)
        G = geo.pullback(torch.stack(C), L, "cos")
        q = geo.fit_quality(torch.stack(C), G, L, "cos")
        out["layers"][L] = {k: G[j].cpu() for j, k in enumerate(keys)}
        top = C[-1].topk(25).indices.tolist()
        out["decode"][L] = {"top": lens.display(top), "fit_quality": q.tolist(), "scale": s_L}
        md.append(f"- L{L}: scale {s_L:.3f}, pullback residual {q[-1]:.2f}; {' '.join(repr(x) for x in lens.display(top))}")
        print(md[-1] + f" ({time.time() - t:.0f}s)", flush=True)
    root = OUT / "priors" / "S20b"
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f"readfreq-k{args.k}.tmp"
    torch.save(out, tmp)
    tmp.rename(root / f"readfreq-k{args.k}.pt")
    (root / f"readfreq-k{args.k}.md").write_text("\n".join(md) + "\n")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
