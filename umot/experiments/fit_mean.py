"""The J-lens fit mean μ_fit, and whether the averaged Jacobian is the fit distribution's regression slope.

The released J-lens (``neuronpedia/jacobian-lens`` n1000 wikitext) stores only ``J``. Its fit is
``jlens.fitting.fit`` with the package defaults: the first 1000 WikiText-103 train records with
>= 600 characters (``jlens.examples.load_wikitext_prompts``), truncated to 128 tokens, positions
16 .. L-2, the Jacobian averaged over positions within a prompt and then over prompts. This
replays exactly that pass (``jlens.from_hf`` and its ``ActivationRecorder``, block-L outputs) without
the backward passes, and records:

1. ``mu.pt``: μ_fit per layer 0..63, weighted as J is (per-prompt position mean, then prompt mean;
   ``mu``), plus the plain token-weighted mean (``mu_tok``). The centre for ``J_l (h − μ_fit,l)``.
2. The cheap test (Stein's lemma: for Gaussian h, E[∂f/∂h] = Cov(f, h) Σ⁻¹, the OLS slope with
   intercept at the mean). On prompts < ``--test-from``: ridge OLS of the final residual (block 63,
   same position) on h_l. On held-out prompts: R² of y − μ_y predicted by J_l (x − μ_l), by the OLS
   slope, and by J_l x with no centring; next-token top-1 of each affine prediction through the
   model's own norm + LM head; and how close the OLS slope is to J_l. Caveat: J sums the effect on
   every LATER final position (the fit's estimator); the regression is same-position only.

  # pod (from the repo root, in tmux):  .venv/bin/python experiments/fit_mean.py --device cuda
  # local smoke (cached 0.8B and its lens):
  .venv/bin/python experiments/fit_mean.py --model Qwen/Qwen3.5-0.8B \
      --lens-file qwen3.5-0.8b/jlens/Salesforce-wikitext/Qwen3.5-0.8B_jacobian_lens.pt \
      --n-prompts 24 --test-from 16 --ols-layers 4,12,20 --out out/smoke/fitmean
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from umot.provenance import PINS, Provenance, write_artefact  # noqa: E402

LENS_REPO = "neuronpedia/jacobian-lens"
LENS_FILE = "qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt"
GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]  # the capture layers
RIDGE = (1e-4, 1e-3, 1e-2, 1e-1)  # λ / (tr Σ / d)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", default="Qwen/Qwen3.6-27B")
    ap.add_argument("--lens-file", default=LENS_FILE)
    ap.add_argument("--n-prompts", type=int, default=1000)
    ap.add_argument("--max-seq-len", type=int, default=128)
    ap.add_argument("--skip-first", type=int, default=16)
    ap.add_argument("--test-from", type=int, default=800, help="prompts >= this are the OLS held-out set")
    ap.add_argument("--ols-layers", default=",".join(map(str, GRID)))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out" / "fitmean")
    args = ap.parse_args()
    from huggingface_hub import HfApi, hf_hub_download
    from jlens.examples import load_wikitext_prompts
    from jlens.fitting import valid_position_mask
    from jlens.hf import from_hf
    from jlens.hooks import ActivationRecorder
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev, f64 = args.device, torch.float64
    rev = PINS.get(args.model)
    tok = AutoTokenizer.from_pretrained(args.model, revision=rev)
    hf = AutoModelForCausalLM.from_pretrained(args.model, revision=rev, dtype=torch.bfloat16, device_map=dev).eval()
    lm = from_hf(hf, tok)
    n_blocks, d = lm.n_layers, lm.d_model
    target = n_blocks - 1
    ols_layers = [int(x) for x in args.ols_layers.split(",")]

    prompts = load_wikitext_prompts(args.n_prompts)
    wikitext_sha = HfApi().dataset_info("Salesforce/wikitext").sha
    prompts_sha = hashlib.sha256("\x00".join(prompts).encode()).hexdigest()
    print(f"{len(prompts)} prompts (wikitext @ {wikitext_sha}, sha256 {prompts_sha[:12]})", flush=True)

    mu_p = torch.zeros(n_blocks, d, dtype=f64, device=dev)  # sum over prompts of the position mean
    mu_t = torch.zeros(n_blocks, d, dtype=f64, device=dev)  # sum over tokens
    n_tok = n_prompts = 0
    acc = {L: {"sx": torch.zeros(d, dtype=f64, device=dev), "sy": torch.zeros(d, dtype=f64, device=dev),
               "xx": torch.zeros(d, d, dtype=f64, device=dev), "xy": torch.zeros(d, d, dtype=f64, device=dev)}
           for L in ols_layers}
    n_fit = 0
    test_x: dict[int, list[torch.Tensor]] = {L: [] for L in ols_layers}
    test_y: list[torch.Tensor] = []
    test_next: list[torch.Tensor] = []
    t0 = time.time()
    with torch.no_grad(), ActivationRecorder(lm.layers, at=range(n_blocks)) as rec:
        for k, text in enumerate(prompts):
            ids = lm.encode(text, max_length=args.max_seq_len)
            try:
                pos = valid_position_mask(ids.shape[1], skip_first=args.skip_first).nonzero().squeeze(1)
            except ValueError:
                continue  # the fit skips too-short prompts the same way
            lm.forward(ids)
            H = {L: rec.activations[L][0, pos.to(rec.activations[L].device)].to(dev, f64) for L in range(n_blocks)}
            for L in range(n_blocks):
                mu_p[L] += H[L].mean(0)
                mu_t[L] += H[L].sum(0)
            n_prompts += 1
            n_tok += len(pos)
            y = H[target]
            if k < args.test_from:
                for L in ols_layers:
                    a, x = acc[L], H[L]
                    a["sx"] += x.sum(0); a["sy"] += y.sum(0); a["xx"] += x.T @ x; a["xy"] += x.T @ y
                n_fit += len(pos)
            else:
                for L in ols_layers:
                    test_x[L].append(H[L].to(torch.bfloat16).cpu())
                test_y.append(y.to(torch.bfloat16).cpu())
                test_next.append(ids[0, pos + 1].cpu())
            if k % 50 == 0:
                print(f"  prompt {k}/{len(prompts)}  {time.time() - t0:.0f}s", flush=True)
    rec.activations.clear()

    args.out.mkdir(parents=True, exist_ok=True)
    mu = (mu_p / n_prompts).float().cpu()
    torch.save({"mu": {L: mu[L] for L in range(n_blocks)}, "mu_tok": {L: (mu_t[L] / n_tok).float().cpu() for L in range(n_blocks)},
                "n_prompts": n_prompts, "n_tokens": n_tok}, args.out / "mu.pt")
    print(f"mu.pt: {n_prompts} prompts, {n_tok} positions; |mu| L20/42/60/{target}: "
          + " / ".join(f"{mu[L].norm():.1f}" for L in (20, 42, 60, target) if L < n_blocks), flush=True)

    # The cheap test.
    lens = torch.load(hf_hub_download(LENS_REPO, args.lens_file, revision=PINS[LENS_REPO]), map_location="cpu",
                      weights_only=False, mmap=True)
    Ytest = torch.cat(test_y).to(dev, f64)
    nxt = torch.cat(test_next).to(dev)
    mu_y = (acc[ols_layers[0]]["sy"] / n_fit)  # same for every layer
    Yc = Ytest - mu_y
    ss = (Yc**2).sum()

    def r2(pred: torch.Tensor) -> float:
        return float(1 - ((Yc - pred) ** 2).sum() / ss)

    def top1(resid: torch.Tensor) -> float:
        hits = 0
        for a in range(0, resid.shape[0], 512):
            hits += int((lm.unembed(resid[a : a + 512].to(torch.bfloat16)).argmax(-1).to(nxt.device) == nxt[a : a + 512]).sum())
        return hits / resid.shape[0]

    rows = []
    betas = {}
    for L in ols_layers:
        a = acc[L]
        mx, my = a["sx"] / n_fit, a["sy"] / n_fit
        Sxx = a["xx"] / n_fit - torch.outer(mx, mx)
        Sxy = a["xy"] / n_fit - torch.outer(mx, my)
        J = lens["J"][L].to(dev, f64)  # (out, in): y ≈ J x
        X = torch.cat(test_x[L]).to(dev, f64)
        Xc = X - mx
        pj = Xc @ J.T
        row = {"layer": L, "n_fit": n_fit, "n_test": X.shape[0],
               "r2_J_ctr": r2(pj), "r2_J_plain": float(1 - ((Ytest - X @ J.T) ** 2).sum() / ss),
               "alpha_J": float((pj * Yc).sum() / (pj**2).sum()),
               "top1_J_ctr": top1(mu_y + pj), "top1_J_plain": top1(X @ J.T), "top1_mean_only": top1(mu_y.expand_as(Ytest))}
        row["r2_J_ctr_scaled"] = r2(row["alpha_J"] * pj)
        lam0 = float(torch.trace(Sxx)) / d
        best = None
        for r in RIDGE:
            B = torch.linalg.solve(Sxx + r * lam0 * torch.eye(d, dtype=f64, device=dev), Sxy)  # (in, out): y ≈ x B
            score = r2(Xc @ B)
            row[f"r2_ols_{r:g}"] = score
            if best is None or score > best[0]:
                best = (score, r, B)
        _s, r, B = best
        row["ols_ridge"] = r
        row["top1_ols"] = top1(mu_y + Xc @ B)
        Bt = B.T  # (out, in), comparable with J
        row["ols_vs_J_cos"] = float((Bt * J).sum() / (Bt.norm() * J.norm()))
        row["ols_vs_J_relfro"] = float((Bt - J).norm() / J.norm())
        # Directions that matter: J and the slope applied to the held-out deviations.
        pb = Xc @ B
        row["pred_cos_ols_J"] = float(torch.nn.functional.cosine_similarity(pb, pj, dim=1).mean())
        betas[L] = Bt.to(torch.float16).cpu()
        rows.append(row)
        print("  " + "  ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in row.items()), flush=True)
    torch.save({"beta": betas, "note": "ridge OLS slope (out, in): y_63 - mu_y ≈ beta (h_l - mu_l), same position"},
               args.out / "ols_beta.pt")

    prov = Provenance(model=args.model, model_revision=rev or "", reader=LENS_REPO, reader_revision=PINS[LENS_REPO],
                      dataset=f"Salesforce/wikitext wikitext-103-raw-v1 train @ {wikitext_sha}", seed=0,
                      extra={"lens_file": args.lens_file, "n_prompts_requested": args.n_prompts, "max_seq_len": args.max_seq_len,
                             "skip_first": args.skip_first, "test_from": args.test_from, "prompts_sha256": prompts_sha,
                             "ridge": RIDGE, "device": dev, "recipe": "jlens.fitting.fit defaults (load_wikitext_prompts, 128, 16)"})
    write_artefact(args.out / "summary.json", prov, {"n_prompts": n_prompts, "n_tokens": n_tok, "ols": rows})
    print(f"done {time.time() - t0:.0f}s -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
