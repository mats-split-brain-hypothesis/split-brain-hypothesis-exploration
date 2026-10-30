"""Programme LL, phase 1 diagnostics (plan.md §4, LL1): router geometry, where bank cells land, expert agreement.

    python experiments/ll1_diag.py [--experts]       # Mac-light without --experts (routers + captures only)

Without ``--experts``: per router and layer, the share of each dev family's fit / val cells in each cluster (do val
cells land in the clusters fit cells occupy? does the wikitext router put all our cells in one cluster?).
With ``--experts`` (pod: loads the merged experts): ``||mu_i|| / mean ||h||`` per expert, inter-expert cosine of J
per layer (Fig 17 of J++ on ours), each expert's cosine to the pooled J and to the n1000 lens, the split-half
cosine (noise floor) of w1 and w8, and the gate: cos(w1, n1000) per layer.
Writes ``out/analysis/LL1/{landing,experts}.json``.
"""

import argparse
import json
from pathlib import Path

import torch

from jlm import OUT, banks, capture
from jlm.mu.LL0 import Router

LL0 = OUT / "analysis" / "LL0"
ROOT = OUT / "analysis" / "LL1"
EXPERTS = Path("/root/ll0-ckpt/experts")


def cos(a: torch.Tensor, b: torch.Tensor) -> float:
    a, b = a.flatten().double(), b.flatten().double()
    return float(a @ b / (a.norm() * b.norm()))


def landing(routers: dict[str, Router], layers: list[int]) -> dict:
    fams = banks.dev_families()
    out = {}
    for f in fams:
        for split in ("fit", "val"):
            try:
                items = capture.load(banks.load(f, split))
            except (FileNotFoundError, RuntimeError):
                continue
            for L in layers:
                H = torch.cat([it.acts[L].float() for it in items if L in it.acts])
                for name, r in routers.items():
                    if r.kind == "random" or r.k == 1:
                        continue
                    c = torch.bincount(r.assign(H, L, 0) % r.k, minlength=r.k)
                    out.setdefault(name, {}).setdefault(str(L), {}).setdefault(f, {})[split] = (c.float() / c.sum()).tolist()
        print("landing", f, flush=True)
    return out


def experts(layers: list[int]) -> dict:
    from jlm.lens import load_maps

    n1000 = load_maps("jlens", layers)
    out = {}
    for L in layers:
        ex = torch.load(EXPERTS / f"experts-L{L:03d}.pt", weights_only=False)
        acts = torch.load(LL0 / f"wiki-acts-L{L:03d}.pt").float()
        hn = float(acts.norm(dim=1).mean())
        J1 = ex["w1"]["J"][0].float()
        rec = {"gate_cos_w1_n1000": cos(J1, n1000[L]), "h_norm": hn,
               "relnorm_w1_n1000": float(J1.norm() / n1000[L].norm())}
        h = ex["w1:halves"]["J"].float()
        rec["split_half_w1"] = cos(h[0], h[1])
        h8 = ex["w8:halves"]["J"].float()
        rec["split_half_w8"] = [cos(h8[i], h8[i + 8]) for i in range(8)]
        for name in [k for k in ex if ":" not in k and k != "w1"]:
            J, mu, c = ex[name]["J"].float(), ex[name]["mu"], ex[name]["count"]
            k = len(c)
            C = [[round(cos(J[i], J[j]), 4) for j in range(k)] for i in range(k)]
            rec[name] = {"count": c.tolist(), "mu_rel_norm": [float(mu[i].norm() / hn) for i in range(k)],
                         "cos_pool": [cos(J[i], J1) for i in range(k)], "cos_n1000": [cos(J[i], n1000[L]) for i in range(k)],
                         "inter_cos": C, "rel_norm_pool": [float(J[i].norm() / J1.norm()) for i in range(k)]}
        out[str(L)] = rec
        print(L, {k: v for k, v in rec.items() if k.startswith(("gate", "split", "relnorm"))}, flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experts", action="store_true")
    a = ap.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    rs = torch.load(LL0 / "routers.pt", weights_only=False)
    routers = {s["name"]: Router.from_state(s) for s in rs["routers"]}
    if a.experts:
        (ROOT / "experts.json").write_text(json.dumps(experts(rs["layers"])))
    else:
        (ROOT / "landing.json").write_text(json.dumps(landing(routers, rs["layers"])))


if __name__ == "__main__":
    main()
