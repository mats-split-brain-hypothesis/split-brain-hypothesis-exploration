"""x20 / x21: one pass over the released J-lens's own fitting cells.

  python experiments/x20_fit_distribution.py --device cuda [--n 1000]

The n1000 lens (jlens 0.1.0: ``fitting.fit`` over ``examples.load_wikitext_prompts``): the first 1000
wikitext-103-raw TRAIN records of >= 600 characters, raw, truncated to 128 tokens (no BOS: Qwen3.6 has none, so
``force_bos`` adds nothing), source positions 16 .. seq_len - 2 (``fitting.valid_position_mask``). The read layers'
states and the final block's output h_63 (the lens's target layer) at those cells, accumulated in fp64:

  x20  fitmu: per layer, the mean of h_l over prompts of the mean over each prompt's cells (J's own weighting).
       -> out/captures/fitmu.pt (constant_mu.LensFitMean).
  x21  B_l = C_l (Σ_l + λI)^-1, C_l = Cov(h_63, h_l), Σ_l = Cov(h_l) over all cells, λ = 1e-3 tr(Σ_l) / d: the
       least-squares slope of h_63 on h_l, which Stein's lemma would equate with the average Jacobian if h_l were
       Gaussian. -> out/maps/ols.pt (read as ``ols:``, jlm.lens.MAPS), and out/x21/compare.json: per layer, cos(vec B,
       vec J) and ||B - J||_F / ||J||_F for the J-lens and J++, the same between the J-lens and J++ (the scale of a
       difference between two working lenses), and the variance of h_63 each map explains on held-out prompts (the
       slope fitted on even prompts, every map scored on odd ones).
"""

import argparse
import gc
import json

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, banks, hfdata
from jlm.capture import MODEL, load_backend
from jlm.lens import LENSES, load_maps, reader

WIKITEXT = "Salesforce/wikitext"
MIN_CHARS, MAX_LEN, SKIP_FIRST, TARGET = 600, 128, 16, 63  # jlens 0.1.0 defaults; TARGET = n_layers - 1
RIDGE = 1e-3
FITMU = OUT / "captures" / "fitmu.pt"
OLS = OUT / "maps" / "ols.pt"
COMPARE = OUT / "x21" / "compare.json"


def wikitext_prompts(n: int) -> list[str]:
    """``jlens.examples.load_wikitext_prompts(n)`` at the pinned dataset revision."""
    import datasets

    from jlm import wikitext

    ds = datasets.load_dataset(WIKITEXT, "wikitext-103-raw-v1", split="train", streaming=True, revision=wikitext.REVISION)
    out = []
    for rec in ds:
        if len(rec["text"].strip()) >= MIN_CHARS:
            out.append(rec["text"])
            if len(out) == n:
                break
    return out


class Moments:
    """fp64 sums over cells for one half of the prompts: Σx, Σy, Σxxᵀ, Σyxᵀ per layer, and Σ||y||²."""

    def __init__(self, layers: list[int], d: int, device: str) -> None:
        def z(*shape):
            return torch.zeros(*shape, dtype=torch.float64, device=device)

        self.n, self.yy = 0, 0.0
        self.sy = z(d)
        self.sx = {L: z(d) for L in layers}
        self.xx = {L: z(d, d) for L in layers}
        self.yx = {L: z(d, d) for L in layers}

    def add(self, acts: dict[int, torch.Tensor], y: torch.Tensor) -> None:
        self.n += y.shape[0]
        self.yy += float(y.square().sum())
        self.sy += y.sum(0)
        for L, x in acts.items():
            self.sx[L] += x.sum(0)
            self.xx[L].addmm_(x.T, x)
            self.yx[L].addmm_(y.T, x)

    def absorb(self, o: "Moments") -> None:
        self.n, self.yy, self.sy = self.n + o.n, self.yy + o.yy, self.sy + o.sy
        for L in self.sx:
            self.sx[L] += o.sx[L]
            self.xx[L] += o.xx[L]
            self.yx[L] += o.yx[L]

    def cov(self, L: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, float]:
        """(m_x, m_y, Σ_x, C = Cov(y, x), tr Σ_y)."""
        mx, my = self.sx[L] / self.n, self.sy / self.n
        return (mx, my, self.xx[L] / self.n - torch.outer(mx, mx), self.yx[L] / self.n - torch.outer(my, mx),
                self.yy / self.n - float(my @ my))


def slope(m: Moments, L: int) -> torch.Tensor:
    _, _, sx, c, _ = m.cov(L)
    lam = RIDGE * float(sx.diagonal().sum()) / sx.shape[0]
    return torch.linalg.solve(sx + lam * torch.eye(sx.shape[0], dtype=sx.dtype, device=sx.device), c.T).T


def explained(m: Moments, L: int, A: torch.Tensor) -> float:
    """1 - E||(y - m_y) - A (x - m_x)||² / E||y - m_y||² on the cells of ``m`` (centred at their own means)."""
    _, _, sx, c, ty = m.cov(L)
    return 1 - (ty - 2 * float((A * c).sum()) + float(((A @ sx) * A).sum())) / ty


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    layers = sorted({L for f in ("typo", "user_modeling", "directed_modulation") for L in banks.specs(banks.load(f, "val"))[0].layers})
    prompts = wikitext_prompts(args.n)
    backend = load_backend(args.device)
    tok, blocks = backend.tokenizer, backend.blocks
    d = backend.model.config.get_text_config().hidden_size
    assert len(blocks) - 1 == TARGET, f"target layer {TARGET} is not the last of {len(blocks)} blocks"
    halves = [Moments(layers, d, args.device), Moments(layers, d, args.device)]
    mean_sum = {L: torch.zeros(d, dtype=torch.float64, device=args.device) for L in layers}
    store: dict[int, torch.Tensor] = {}
    window = slice(0, 0)

    def make(L: int):
        def hook(_m, _i, out):
            h = out[0] if isinstance(out, tuple) else out
            store[L] = h[0, window].double()
        return hook

    handles = [blocks[L].register_forward_hook(make(L)) for L in [*layers, TARGET]]
    n_cells = n_used = 0
    try:
        for k, text in enumerate(prompts):
            ids = tok(text, truncation=True, max_length=MAX_LEN)["input_ids"]
            window = slice(SKIP_FIRST, len(ids) - 1)
            if len(ids) - 1 <= SKIP_FIRST:
                continue
            backend.model(torch.tensor([ids], device=backend.model.device), logits_to_keep=1)
            y = store.pop(TARGET)
            acts = {L: store.pop(L) for L in layers}
            halves[k % 2].add(acts, y)
            for L in layers:
                mean_sum[L] += acts[L].mean(0)
            n_cells += y.shape[0]
            n_used += 1
            if k % 100 == 0:
                print(f"{k}/{len(prompts)} prompts, {n_cells} cells", flush=True)
    finally:
        for h in handles:
            h.remove()
    del backend, blocks, handles  # free the model before the d x d solves
    gc.collect()
    torch.cuda.empty_cache()

    fitmu = {L: (mean_sum[L] / n_used).float().cpu() for L in layers}
    FITMU.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"mean": fitmu, "n_prompts": n_used, "n_cells": n_cells}, FITMU)
    recipe = {"dataset": f"{WIKITEXT}/wikitext-103-raw-v1/train", "min_chars": MIN_CHARS, "max_len": MAX_LEN,
              "positions": f"{SKIP_FIRST} .. seq_len - 2", "n_prompts": n_used, "n_cells": n_cells, "target_layer": TARGET}
    write_artefact(FITMU.with_suffix(".provenance.json"),
                   Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=recipe["dataset"],
                              extra={**recipe, "weighting": "mean over prompts of each prompt's mean over its cells"}),
                   {"layers": layers})
    print(f"fitmu: {n_used} prompts, {n_cells} cells", flush=True)

    even, odd = halves
    full = Moments(layers, d, args.device)
    full.absorb(even)
    full.absorb(odd)
    rows = {}
    B = {}
    for L in layers:
        B[L] = slope(full, L)
        b_even = slope(even, L)
        J = {name: load_maps(name, [L], args.device)[L].double() for name in ("jlens", "jpp")}

        def cmp(a, b):
            return {"cos": float((a * b).sum() / (a.norm() * b.norm())), "rel_frob": float((a - b).norm() / b.norm())}

        rows[L] = {
            "ols_vs_jlens": cmp(B[L], J["jlens"]), "ols_vs_jpp": cmp(B[L], J["jpp"]), "jpp_vs_jlens": cmp(J["jpp"], J["jlens"]),
            "r2_heldout": {"ols(even)": explained(odd, L, b_even), "jlens": explained(odd, L, J["jlens"]),
                           "jpp": explained(odd, L, J["jpp"])},
            "intercept_rel": {name: float((full.cov(L)[1] - A @ full.cov(L)[0]).norm() / full.cov(L)[1].norm())
                              for name, A in (("ols", B[L]), *J.items())},
        }
        print(f"L{L}: cos(B, J) {rows[L]['ols_vs_jlens']['cos']:+.3f}  cos(B, J++) {rows[L]['ols_vs_jpp']['cos']:+.3f}  "
              f"cos(J++, J) {rows[L]['jpp_vs_jlens']['cos']:+.3f}  R2 held-out "
              + "  ".join(f"{k} {v:.3f}" for k, v in rows[L]["r2_heldout"].items()), flush=True)
        B[L] = B[L].float().cpu()
        del J, b_even
        torch.cuda.empty_cache()

    OLS.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"J": B, "ridge": RIDGE, **recipe}, OLS)
    COMPARE.parent.mkdir(parents=True, exist_ok=True)
    COMPARE.write_text(json.dumps({"recipe": recipe, "ridge": RIDGE, "layers": {str(L): r for L, r in rows.items()}},
                                  indent=1) + "\n")
    for p in (OLS, COMPARE):
        write_artefact(p.with_suffix(".provenance.json"),
                       Provenance(model=MODEL, model_revision=PINS[MODEL], dataset=recipe["dataset"],
                                  reader="/".join(LENSES["jlens"]), reader_revision=reader("jlens")[1],
                                  extra={**recipe, "ridge": RIDGE, "split": "B on all cells; held-out R2: B on even prompts, scored on odd"}),
                       {"layers": layers})
    hfdata.share([FITMU, FITMU.with_suffix(".provenance.json"), OLS, OLS.with_suffix(".provenance.json"),
                  COMPARE.parent])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
