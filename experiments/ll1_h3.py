"""Programme LL, H3 (plan.md §2, LL1): the first-order error of the lens by expansion point, on held-out positions.

    python experiments/ll1_h3.py --prompts 900:924 --per-prompt 8 [--experts DIR]

For a held-out wikitext position s at layer L with state h, and an anchor m, patch the block-L output at s to m, run
the rest of the network, and take what the lens linearises: ``F(x) = sum_{kept t >= s} h_final[t]`` (the J-lens
estimator's target, jlens.fitting). Error of slope J at anchor m:

    e(m, J) = || F(h) - F(m) - J (h - m) || / || F(h) - F(m) ||

Anchors: ``zero``, ``glob`` (the sweep's pooled mean), ``own`` (mu of h's w8 cluster), ``other`` (mu of another w8
cluster: control), ``knn`` (mean of the 8 nearest router pre-pass states, cosine, prompts 0-399 so disjoint).
Slopes: ``pool`` (our w1 J), ``n1000`` (released), ``own`` (h's w8 expert J_i). Held-out prompts lie beyond the
sweep's and the router's prompts. Writes ``out/analysis/LL1/h3.json`` (per layer, anchor, slope: mean / median
error, plus ||h - m|| / ||h||).
"""

import argparse
import json
import time
from pathlib import Path

import torch

from jlm import OUT
from jlm.mu.LL0 import MAX_SEQ_LEN, SKIP_FIRST, Router

LAYERS = [24, 32, 40, 48, 56]
LL0 = OUT / "analysis" / "LL0"
EXPERTS = Path("/root/ll0-ckpt/experts")


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="900:924")
    ap.add_argument("--per-prompt", type=int, default=8)
    ap.add_argument("--experts", default=str(EXPERTS))
    ap.add_argument("--rows", type=int, default=32, help="patched sequences per forward")
    ap.add_argument("--eps", type=float, default=0.1, help="finite-difference step for the local tangent (0: off)")
    ap.add_argument("--out", default="h3.json")
    a = ap.parse_args()
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from ll0_sweep import load_model, wiki

    from jlm.lens import load_maps

    lo, hi = map(int, a.prompts.split(":"))
    prompts = wiki(1000)[lo:hi]
    model = load_model()
    dev = "cuda"
    rs = torch.load(LL0 / "routers.pt", weights_only=False)
    w8 = Router.from_state(next(s for s in rs["routers"] if s["name"] == "w8"))
    n1000 = load_maps("jlens", LAYERS, dev)
    target = model.n_layers - 1
    res = {}
    g = torch.Generator().manual_seed(0)
    for L in LAYERS:
        ex = torch.load(Path(a.experts) / f"experts-L{L:03d}.pt", weights_only=False)
        Jpool = ex["w1"]["J"][0].to(dev, torch.float32)
        J8, mu8 = ex["w8"]["J"].to(dev, torch.float32), ex["w8"]["mu"].to(dev)
        glob = ex["w1"]["mu"][0].to(dev)
        ref = torch.load(LL0 / f"wiki-acts-L{L:03d}.pt").to(dev, torch.float32)
        refu = ref / ref.norm(dim=1, keepdim=True)
        errs = {}
        for pi, p in enumerate(prompts):
            ids = model.encode(p, max_length=MAX_SEQ_LEN)
            S = ids.shape[1]
            if S <= SKIP_FIRST + 2:
                continue
            kept = torch.arange(SKIP_FIRST, S - 1)
            pos = kept[torch.randperm(len(kept), generator=g)[: a.per_prompt]].tolist()
            store = {}

            def rec(_m, _i, out):
                store["h"] = (out[0] if isinstance(out, tuple) else out).detach()

            def fin(_m, _i, out):
                store["f"] = (out[0] if isinstance(out, tuple) else out).detach().float()

            hd = [model.layers[L].register_forward_hook(rec), model.layers[target].register_forward_hook(fin)]
            with torch.no_grad():
                model.forward(ids)
            for x in hd:
                x.remove()
            H, F0 = store["h"][0].float(), store["f"][0]
            jobs = []  # (s, cluster, anchor name, m)
            Fpat = {}
            for s in pos:
                h = H[s]
                c = int(w8.assign(h[None], L, 0)[0])
                sim = refu @ (h / h.norm())
                knn = ref[sim.topk(8).indices].mean(0)
                for name, m in (("zero", torch.zeros_like(h)), ("glob", glob), ("own", mu8[c]), ("other", mu8[(c + 1) % 8]),
                                ("knn", knn)):
                    jobs.append((s, c, name, m))
                    if a.eps:  # the local tangent at m along h - m, by a finite difference (H3 proper)
                        jobs.append((s, c, name + "+eps", m + a.eps * (h - m)))
            for b in range(0, len(jobs), a.rows):
                chunk = jobs[b : b + a.rows]
                patch = torch.stack([m for _, _, _, m in chunk])
                ss = torch.tensor([s for s, _, _, _ in chunk], device=dev)

                def put(_m, _i, out):
                    t = out[0] if isinstance(out, tuple) else out
                    t[torch.arange(len(chunk), device=t.device), ss] = patch.to(t.dtype)
                    return out

                hd = [model.layers[L].register_forward_hook(put), model.layers[target].register_forward_hook(fin)]
                with torch.no_grad():
                    model.forward(ids.expand(len(chunk), -1))
                for x in hd:
                    x.remove()
                Fm = store["f"]
                for j, (s, c, name, m) in enumerate(chunk):
                    Fpat[(s, name)] = Fm[j, s : S - 1].sum(0)  # F at the patched input, summed over kept t >= s
            for s, c, name, m in jobs:
                if name.endswith("+eps"):
                    continue
                F0s = F0[s : S - 1].sum(0)
                dF = F0s - Fpat[(s, name)]  # F(h) - F(m)
                dh = H[s] - m
                slopes = [("pool", Jpool @ dh), ("n1000", n1000[L] @ dh), ("own", J8[c] @ dh)]
                if a.eps:  # the local tangent at m along h - m: [F(m + eps (h - m)) - F(m)] / eps
                    slopes.append(("local", (Fpat[(s, name + "+eps")] - Fpat[(s, name)]) / a.eps))
                for sl, lin in slopes:
                    errs.setdefault(f"{name}|{sl}", []).append(float((dF - lin).norm() / dF.norm().clamp_min(1e-9)))
                    errs.setdefault(f"{name}|{sl}|cos", []).append(float(dF @ lin / (dF.norm() * lin.norm()).clamp_min(1e-9)))
                    errs.setdefault(f"{name}|{sl}|ratio", []).append(float(lin.norm() / dF.norm().clamp_min(1e-9)))
                errs.setdefault(f"{name}|dist", []).append(float(dh.norm() / H[s].norm()))
                errs.setdefault(f"{name}|dF_rel", []).append(float(dF.norm() / F0s.norm()))
            Fpat.clear()
            if pi % 8 == 0:
                log(L, pi, {k: round(sum(v) / len(v), 3) for k, v in errs.items() if k.endswith(("|pool", "|local"))})
        res[str(L)] = {k: {"mean": sum(v) / len(v), "median": float(torch.tensor(v).median()), "n": len(v)} for k, v in errs.items()}
        log("L", L, {k: round(v["median"], 3) for k, v in res[str(L)].items() if "|cos" not in k})
        log("L", L, "cos", {k: round(v["median"], 3) for k, v in res[str(L)].items() if "|cos" in k})
        (OUT / "analysis" / "LL1").mkdir(parents=True, exist_ok=True)
        (OUT / "analysis" / "LL1" / a.out).write_text(json.dumps(res, indent=1))
    log("H3_DONE")


if __name__ == "__main__":
    main()
