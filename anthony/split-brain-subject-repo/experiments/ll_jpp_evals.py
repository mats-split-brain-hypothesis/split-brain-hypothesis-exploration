"""Programme LL, the second scorer: our maps on J++'s held-out readout evals (plan.md §5), and H5 on J++'s ground.

    python experiments/ll_jpp_evals.py --device cuda [--refit w8,o8]

Uses umot's capture of the five J++ readout evals (``umot/out/jpp/residuals.pt``: one read cell per item, every
layer; ``items.json``: eval, the J++ fit / held / incorrect split, seed 0, 20 % fit). Scored as the paper (and
umot's ``jpp_compare.py``): readout ``rms`` (final norm then W_U; the paper's) with Readout Filtering (ids whose decode
has no letter or digit excluded, candidates spared), rank = 1 + #(logits > best candidate logit), recall@10 = mean over
an eval's (item, intermediate) pairs of min-rank-over-layers <= 10, macro over the five evals, held-out items only.
Check: the released maps on the 7 recipe layers must give J++ 0.594 / n1000 0.340 (umot's numbers).

Maps x anchors on our 5 layers (24..56): n1000, jpp, pool (our w1), and per router the expert weights refitted on
J++'s fit split (their protocol, our plain-gradient experts) with anchors none / ref (the eval's fit-split mean,
umot's ``ref``) / own (paired ``sum w_e J_e (h - mu_e)``), plus the LL4 weights (fitted on our banks) if present.
Writes ``out/analysis/LLjpp/scores.json``.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).parent))
from ll4_fitw import fit_layer  # noqa: E402

from jlm import OUT, REPO_ROOT, controls  # noqa: E402
from jlm.lens import RMS_EPS, Lens, load_maps  # noqa: E402

RECIPE = [8, 16, 24, 32, 40, 48, 56]
OURS = [24, 32, 40, 48, 56]
JPP = REPO_ROOT / "umot" / "out" / "jpp"
EXPERTS = Path("/root/ll0-ckpt/experts")
MIN_COUNT = 200


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--experts", default=str(EXPERTS))
    ap.add_argument("--refit", default="w8,o8")
    ap.add_argument("--jpp-dir", default=str(JPP), help="residuals.pt + items.json (umot's capture)")
    a = ap.parse_args()
    dev = a.device
    res = torch.load(Path(a.jpp_dir) / "residuals.pt", weights_only=False)
    meta = json.loads((Path(a.jpp_dir) / "items.json").read_text())
    R = res["residuals_L_dict_PN"]
    cands = res["candidate_ids_by_item"]
    lens = Lens(OURS, dev)
    V = lens.vocab
    spared = {t for c in cands for ids in c.values() for t in ids}
    excl = torch.zeros(V, dtype=torch.bool, device=dev)
    excl[controls.non_semantic_ids(lens.tokenizer, V, spared)] = True
    pairs = [(p, i, c) for p, cs in enumerate(cands) for i, c in cs.items()]
    C = max(len(c) for _, _, c in pairs)
    pair_item = torch.tensor([p for p, _, _ in pairs], device=dev)
    pair_c = torch.tensor([c + [c[0]] * (C - len(c)) for _, _, c in pairs], device=dev)
    evals = sorted({m["eval"] for m in meta})
    pair_eval = torch.tensor([evals.index(meta[p]["eval"]) for p, _, _ in pairs], device=dev)
    split = [m["split"] for m in meta]
    held_pair = torch.tensor([split[p] == "held" for p, _, _ in pairs], device=dev)
    fit_items = torch.tensor([s == "fit" for s in split])

    def logits_rms(Z):  # [n, V]
        Z = Z.to(dev, torch.float32)
        return (lens.gain * Z / torch.sqrt(Z.square().mean(1, keepdim=True) + RMS_EPS)) @ lens.w_u.T

    def pair_ranks(lg):  # [P_pairs]
        lg = lg.masked_fill(excl, float("-inf"))
        per = lg[pair_item]
        best = per.gather(1, pair_c).max(1).values
        return (per >= best[:, None]).sum(1)  # = 1 + #(>) without ties; ties count against (a degenerate all-equal
        # readout, e.g. weight on an empty expert, scored recall 1.0 under 1 + #(>): o8, 2026-10-12)

    def recall(rank_by_layer, mask=held_pair):  # macro over evals of mean hit (min rank over layers <= 10)
        r = torch.stack(rank_by_layer).min(0).values
        hit = (r <= 10).float()
        per = [float(hit[mask & (pair_eval == e)].mean()) for e in range(len(evals))]
        return {"macro": sum(per) / len(per), **dict(zip(evals, per))}

    def ref_mean(L):  # per item: mean of its eval's fit-split items (umot's ``ref``)
        H = R[L].float()
        out = torch.zeros_like(H)
        for e in evals:
            idx = torch.tensor([m["eval"] == e for m in meta])
            out[idx] = H[idx & fit_items].mean(0)
        return out

    scores = {}
    # ---- check: released maps on the recipe layers ----
    rel = {"n1000": load_maps("jlens", RECIPE), "jpp": load_maps("jpp", RECIPE)}
    for name, J in rel.items():
        for layers, tag in ((RECIPE, "recipe7"), (OURS, "ours5")):
            for an in ("none", "ref"):
                rk = []
                for L in layers:
                    X = R[L].float() - (ref_mean(L) if an == "ref" else 0)
                    rk.append(pair_ranks(logits_rms(X.to(dev) @ J[L].to(dev).T)))
                scores[f"{name}|{an}|{tag}"] = recall(rk)
                log(name, an, tag, round(scores[f"{name}|{an}|{tag}"]["macro"], 4))
    del rel
    root = OUT / "analysis" / "LLjpp"
    root.mkdir(parents=True, exist_ok=True)
    (root / "scores.json").write_text(json.dumps(scores, indent=1))
    if not (Path(a.experts) / f"experts-L{OURS[0]:03d}.pt").exists():
        log("no experts: released maps only")
        return
    # ---- our experts ----
    ex = {L: torch.load(Path(a.experts) / f"experts-L{L:03d}.pt", weights_only=False) for L in OURS}
    rk = {an: [] for an in ("none", "ref", "glob")}
    for L in OURS:
        J1 = ex[L]["w1"]["J"][0].to(dev, torch.float32)
        for an in rk:
            g = ref_mean(L) if an == "ref" else ex[L]["w1"]["mu"][0] if an == "glob" else 0
            rk[an].append(pair_ranks(logits_rms((R[L].float() - g).to(dev) @ J1.T)))
    for an, v in rk.items():
        scores[f"pool|{an}|ours5"] = recall(v)
        log("pool", an, round(scores[f"pool|{an}|ours5"]["macro"], 4))
    ll4 = OUT / "analysis" / "LL4"
    for router in a.refit.split(","):
        ws = {"refit": {}}
        if (ll4 / router / "weights.pt").exists():
            ws["ll4"] = torch.load(ll4 / router / "weights.pt")
        for an in ("none", "ref", "own"):
            rk_by = {k: [] for k in ("refit", "pooled", "ll4")}
            for L in OURS:
                E = ex[L][router]
                keep = E["count"] >= MIN_COUNT  # experts fitted from too few positions (o8's starved ones) are left out
                J = E["J"][keep].to(dev, torch.float32)
                mu = E["mu"][keep].to(dev)
                k = J.shape[0]
                H = R[L].float().to(dev)
                if an == "own":
                    T = torch.einsum("eij,pej->pei", J, H[:, None, :] - mu[None])  # [P, k, d]
                else:
                    X = H - (ref_mean(L).to(dev) if an == "ref" else 0)
                    T = torch.einsum("eij,pj->pei", J, X)
                # refit on J++'s fit split (pairs of fit items), their protocol
                fp = [(p, c) for p, _, c in pairs if split[p] == "fit"]
                Lpev = torch.stack([(lens.gain * T[[p for p, _ in fp], e]) @ lens.w_u.T for e in range(k)], 1)
                Lpev = Lpev.masked_fill(excl[None, None], -1e4)
                fam_of = torch.tensor([evals.index(meta[p]["eval"]) for p, _ in fp], device=dev)
                cnt = E["count"][keep].float()
                w, v = fit_layer(Lpev, [torch.tensor(c) for _, c in fp], fam_of, len(evals),
                                 [cnt.clone(), torch.ones(k)] + [torch.eye(k)[e] for e in range(k)])
                ws["refit"][f"{an}|L{L}"] = w.cpu()
                del Lpev
                for kind in rk_by:
                    if kind == "ll4":
                        key = f"{'0' if an == 'none' else an}|L{L}"
                        if "ll4" not in ws or key not in ws["ll4"]:
                            continue
                        wk = ws["ll4"][key].to(dev)
                    else:
                        wk = w if kind == "refit" else (cnt / cnt.sum()).to(dev)
                    Z = torch.einsum("e,pei->pi", wk, T)  # sum_e w_e J_e (x - g_e)
                    rk_by[kind].append(pair_ranks(logits_rms(Z)))
            for kind, v in rk_by.items():
                if len(v) == len(OURS):
                    scores[f"{router}:{kind}|{an}|ours5"] = recall(v)
                    log(router, kind, an, round(scores[f"{router}:{kind}|{an}|ours5"]["macro"], 4))
        torch.save(ws["refit"], root / f"weights-{router}.pt")
        (root / "scores.json").write_text(json.dumps(scores, indent=1))
    (root / "scores.json").write_text(json.dumps(scores, indent=1))
    log("JPP_DONE")


if __name__ == "__main__":
    main()
