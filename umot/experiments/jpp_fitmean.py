"""The J-lens fit-mean centre on the J++ paper's readout evals, re-scored locally from ``out/jpp``.

Reuses the stored residuals (``out/jpp/residuals.pt``, every layer at each item's read cell), the
fit / held-out split recorded in ``out/jpp/items.json`` and ``jpp_compare``'s centres and ranking,
and adds ``fit``: ``h − μ_fit,l`` with μ_fit from ``experiments/fit_mean.py`` (the J-lens's own fit
pass on wikitext; item- and task-independent). The J++ code is not run here: Readout Filtering
(drop ids whose decode has no letter or digit, sparing every candidate id) and recall@k (min rank
over the recipe layers, mean over an item's intermediates, then over items, macro = mean of the
five tasks) are re-implemented from ``jpp_lens@JPP_COMMIT`` and checked against the stored ranks of
the existing centres (``--parity``).

  .venv/bin/python experiments/jpp_fitmean.py --device mps
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "experiments"))
from jpp_compare import RECIPE_LAYERS, centred_inputs, load_jacobian_getter, ranks_for  # noqa: E402
from token_local import RMS_EPS, load_norm, load_unembed  # noqa: E402
from umot.provenance import JPP_COMMIT, PINS, Provenance, write_artefact  # noqa: E402

MODEL = "Qwen/Qwen3.6-27B"
MACRO = ("multihop", "multilingual", "typo", "association", "poetry")
CENTRES = ("none", "loo", "ref", "fit")


def recall(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """[lens x eval] recall@k incl. ``macro`` (their ``pass_at_k_over_layers``, item-weighted)."""
    m = df.groupby(["eval", "lens", "item", "intermediate"])["rank"].min().reset_index()
    per_item = m.assign(hit=m["rank"] <= k).groupby(["eval", "lens", "item"])["hit"].mean()
    tab = per_item.groupby(["lens", "eval"]).mean().unstack("eval")
    tab["macro"] = tab.reindex(columns=list(MACRO)).mean(axis=1, skipna=False)
    return tab


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--lenses", default="jlens,rlens,logit,jpp")
    ap.add_argument("--mu", type=Path, default=REPO_ROOT / "out/fitmean/mu.pt")
    ap.add_argument("--src", type=Path, default=REPO_ROOT / "out/jpp")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out/jpp-fitmean")
    args = ap.parse_args()
    from transformers import AutoTokenizer

    dev = args.device
    res = torch.load(args.src / "residuals.pt", map_location="cpu", weights_only=False, mmap=True)
    meta = json.loads((args.src / "items.json").read_text())
    assert [(m["eval"], m["item"]) for m in meta] == [tuple(k) for k in res["header"]["item_keys"]]
    cands = res["candidate_ids_by_item"]
    fit = torch.tensor([m["split"] == "fit" for m in meta])
    mu = torch.load(args.mu, map_location="cpu")["mu"]

    W = load_unembed(MODEL).to(dev)  # [V, d] bf16; upcast per chunk (fp32 W is 5 GB: swaps a 16 GB Mac)
    CH = 16384
    V = W.shape[0]
    gain = (1 + load_norm(MODEL).float()).to(dev)
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    spare = {i for c in cands for ids in c.values() for i in ids}
    decoded = tok.batch_decode([[i] for i in range(V)])
    excl = torch.tensor([not any(ch.isalnum() for ch in s) and i not in spare for i, s in enumerate(decoded)], device=dev)
    print(f"Readout Filtering: {int(excl.sum())} of {V} ids excluded", flush=True)
    pairs = [(p, inter, c) for p, cs in enumerate(cands) for inter, c in cs.items()]
    C = max(len(c) for _p, _i, c in pairs)
    pair_item = torch.tensor([p for p, _i, _c in pairs], device=dev)
    pair_cands = torch.tensor([c + [-1] * (C - len(c)) for _p, _i, c in pairs], device=dev)

    rows: list[dict] = []
    t0 = time.time()
    for lens in args.lenses.split(","):
        getJ = load_jacobian_getter(lens)
        for L in RECIPE_LAYERS:
            H = res["residuals_L_dict_PN"][L].double()
            X = centred_inputs(H, meta, fit)
            X["fit"] = H - mu[L].double()
            J = getJ(L).to(dev) if getJ else None
            denom = torch.cat([((W[a : a + CH].float() @ J) if J is not None else W[a : a + CH].float()).norm(dim=1)
                               for a in range(0, V, CH)]).clamp_min(1e-9)
            for c in CENTRES:
                Z = X[c].float().to(dev)
                Z = Z @ J.T if J is not None else Z
                for ro in ("rms", "cos"):
                    x = gain * Z / torch.sqrt(Z.square().mean(-1, keepdim=True) + RMS_EPS) if ro == "rms" else Z
                    logits = torch.cat([x @ W[a : a + CH].float().T for a in range(0, V, CH)], dim=1)
                    if ro == "cos":
                        logits = logits / denom
                    rk = ranks_for(logits.masked_fill(excl, float("-inf")), pair_item, pair_cands).tolist()
                    rows += [{"eval": meta[p]["eval"], "lens": f"{lens}|{c}|{ro}|filt", "item": meta[p]["item"],
                              "intermediate": i, "layer": L, "rank": r} for (p, i, _c), r in zip(pairs, rk, strict=True)]
            print(f"  {lens} L{L} {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "ranks.csv.gz", index=False)

    # Parity with the stored pod scoring (existing centres only).
    old = pd.read_csv(args.src / "ranks.csv.gz")
    m = df[df["lens"].str.split("|").str[1] != "fit"].merge(old, on=["eval", "lens", "item", "intermediate", "layer"], suffixes=("", "_pod"))
    top10 = (m["rank"] <= 10) | (m["rank_pod"] <= 10)
    parity = {"n": len(m), "exact": float((m["rank"] == m["rank_pod"]).mean()),
              "top10_disagree": int(((m["rank"] <= 10) != (m["rank_pod"] <= 10)).sum()),
              "max_abs_diff_in_top10": int((m["rank"] - m["rank_pod"]).abs()[top10].max())}
    print("parity vs pod:", parity, flush=True)

    held = {(m_["eval"], m_["item"]) for m_ in meta if m_["split"] == "held"}
    sel = df[[(e, i) in held for e, i in zip(df["eval"], df["item"], strict=True)]]
    tabs = {k: recall(sel, k) for k in (1, 5, 10)}
    print(tabs[10].sort_values("macro", ascending=False).round(3).to_string(), flush=True)
    # Paired item-level bootstrap of fit vs none / ref, recall@10, per lens x readout.
    mr = sel.groupby(["eval", "lens", "item", "intermediate"])["rank"].min().reset_index()
    per_item = mr.assign(hit=mr["rank"] <= 10).groupby(["eval", "lens", "item"])["hit"].mean().unstack("lens")
    gen = torch.Generator().manual_seed(0)
    deltas = {}
    for lens in args.lenses.split(","):
        for ro in ("rms", "cos"):
            for base in ("none", "ref", "loo"):
                a, b = f"{lens}|fit|{ro}|filt", f"{lens}|{base}|{ro}|filt"
                d = (per_item[a] - per_item[b]).reset_index()
                d.columns = ["eval", "item", "d"]
                ev = {e: torch.tensor(g["d"].values) for e, g in d.groupby("eval")}
                point = sum(float(v.mean()) for v in ev.values()) / len(ev)
                boots = torch.stack([sum(v[torch.randint(len(v), (len(v),), generator=gen)].mean() for v in ev.values()) / len(ev)
                                     for _ in range(2000)])
                deltas[f"{lens}|{ro}|fit-{base}"] = [round(point, 4), round(float(boots.quantile(0.025)), 4), round(float(boots.quantile(0.975)), 4)]
    for k, v in deltas.items():
        print(f"  {k}: {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]")
    prov = Provenance(model=MODEL, model_revision=PINS[MODEL], reader="neuronpedia/jacobian-lens",
                      reader_revision=PINS["neuronpedia/jacobian-lens"],
                      dataset=f"jpp_lens@{JPP_COMMIT} readout evals (out/jpp residuals, held-out split)", seed=0,
                      extra={"centres": CENTRES, "fit_mean": str(args.mu.relative_to(REPO_ROOT)), "lenses": args.lenses,
                             "layers": RECIPE_LAYERS, "filter": "reimplemented Readout Filtering", "parity": parity,
                             "bootstrap": "paired, items resampled within task, 2000 draws, macro of task means"})
    write_artefact(args.out / "summary.json", prov, {"recall_held": {k: t.round(4).to_dict(orient="index") for k, t in tabs.items()},
                                                     "delta_recall10_held": deltas, "n_held": len(held)})


if __name__ == "__main__":
    main()
