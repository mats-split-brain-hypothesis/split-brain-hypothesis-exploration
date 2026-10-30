"""J++ comparison: our centred readouts on the J++ paper's readout evals, scored exactly as the paper does.

The J++ Lens (Ayonrinde & Lindsey 2026) changes the lens MAP; centring changes the lens INPUT
(read ``J (h - mu)``). This scores every map x centre on the paper's five latent-variable tasks
(multihop, multilingual, typo, association, poetry) with the paper's own code for items, readout
positions, candidate tokens, the Qwen3.6-27B correctness filter, Readout Filtering, the fit /
held-out split (seed 0, 20 % fit) and recall@k (min rank over the seven readout layers 8..56).

Runs inside the J++ repo's environment (``/root/jpp_lens/.venv``, pinned commit ``JPP_COMMIT``)
so their functions are imported, not re-implemented. Maps: ``jpp`` (koayon/jpp-lenses), ``jlens``
(neuronpedia, the bench's), ``rlens`` (camilablank, the bench's), ``logit`` (identity).

Centres (jlens-edits x99/x100's best arms, per task; one read cell per item; no label is used):

    none     h
    loo      h - mean of every OTHER item of the task (all scoreable items, before the correctness
             filter): x100's ``loo1``, transductive (prompts of scored items, never their targets)
    ref      h - mean of the task's FIT-split items (the J++ expert-weight split, never scored):
             x100's ``dev1``, the held-out centre
    reftok   h - mean of the fit-split items with the same read token (>= 3), else ``ref``: ``devtok1``
    refpco4  ``ref``, then the fit cells' top 4 principal directions removed: ``devpco4``

Readouts: ``rms`` = the paper's (``model.unembed(J x)``: final norm then LM head, bf16 as theirs);
``cos`` = the bench's ``(W_U J x)_t / ||J^T W_U[t]||``. Each with and without Readout Filtering.

  # on the pod, from /root/um, with their venv:
  /root/jpp_lens/.venv/bin/python experiments/jpp_compare.py --jpp-repo /root/jpp_lens --stages capture,score
  ... --limit 4          # plumbing: 4 items per task
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from umot.provenance import JPP_COMMIT, PINS, Provenance, write_artefact  # noqa: E402

MODEL = "Qwen/Qwen3.6-27B"
N_LAYERS = 63  # source layers 0..62 (the final block, 63, is the target)
RECIPE_LAYERS = [8, 16, 24, 32, 40, 48, 56]
MAX_SEQ_LEN = 512  # the paper's RECIPE_READOUT_MAX_SEQ_LEN
SPLIT_SEED, FIT_FRACTION = 0, 0.2
TOK_MIN, N_DIR = 3, 4  # x100's TOK_MIN and N_DIR
KS = (1, 5, 10)
LENSES = {  # name -> (repo, filename); revisions from PINS
    "jpp": ("koayon/jpp-lenses", "qwen3.6-27b/lens.pt"),
    "jlens": (
        "neuronpedia/jacobian-lens",
        "qwen3.6-27b/jlens/Salesforce-wikitext/Qwen3.6-27B_jacobian_lens_n1000.pt",
    ),
    "rlens": ("camilablank/workspace-lenses", "qwen3.6-27b/r-lens/lens.pt"),
    "logit": None,
}
CENTRES = ("none", "loo", "ref", "reftok", "refpco4")
READOUTS = ("rms", "cos")


def jpp_imports(jpp_repo: Path) -> None:
    sys.path.insert(0, str(jpp_repo / "src"))


def load_items(jpp_repo: Path):
    from lens_evals.readout_evals.readout_eval_items import MACRO_EVALS, load_readout_eval_items

    return load_readout_eval_items(str(jpp_repo / "data/jlens/evaluations"), slugs=MACRO_EVALS)


def capture(args, model) -> None:
    """One forward pass per scoreable item (their runner), residual at the readout position at
    every layer 0..62, plus the read token. Before the correctness filter: the centres pool over
    prompts, and scoring applies the filter."""
    from lens_evals.readout_evals.readout_evals import ReadoutEvalRunner, _item_readout_and_candidates

    items = load_items(args.jpp_repo)
    if args.limit:
        seen: dict[str, int] = {}
        items = [it for it in items if (seen.__setitem__(it.eval_slug, seen.get(it.eval_slug, 0) + 1) or seen[it.eval_slug] <= args.limit)]
    runner = ReadoutEvalRunner(model, {}, layers=list(range(N_LAYERS)), max_seq_len=MAX_SEQ_LEN)
    t0 = time.time()
    res = runner.record_residuals(items, cache_path=args.out / "residuals.pt", hf_model_name=MODEL)
    by_key = {(it.eval_slug, it.name): it for it in items}
    meta = []
    for ev, name in res.item_keys:
        r = _item_readout_and_candidates(model, by_key[ev, name], MAX_SEQ_LEN)
        ids = r.input_ids_Int_1S[0]
        tid = int(ids[r.readout_position])
        meta.append({"eval": ev, "item": name, "read_pos": int(r.readout_position), "n_tokens": len(ids),
                     "read_token_id": tid, "read_token": model.tokenizer.decode([tid])})
    (args.out / "items.json").write_text(json.dumps(meta, indent=1))
    print(f"[capture] {res.num_items} items, {time.time() - t0:.0f}s", flush=True)


def load_jacobian_getter(name: str):
    """layer -> fp32 J_l (out, in) for ``h @ J.T``; None for the logit lens."""
    if LENSES[name] is None:
        return None
    from huggingface_hub import hf_hub_download

    repo, fn = LENSES[name]
    obj = torch.load(hf_hub_download(repo, fn, revision=PINS[repo]), map_location="cpu", weights_only=False, mmap=True)
    if "parameters" in obj:
        jac = obj["parameters"]["jacobians"]
    else:
        jac = obj["J"] if "J" in obj else obj["jacobians"]
    if isinstance(jac, dict):
        return lambda L: (jac[L] if L in jac else jac[str(L)]).float()
    return lambda L: jac[L].float()


def principal_directions(H: torch.Tensor, k: int) -> torch.Tensor:
    """jlens-edits x90f: top-k principal directions of the rows of H about their mean, float64."""
    _u, _s, Vh = torch.linalg.svd(H - H.mean(0, keepdim=True), full_matrices=False)
    return Vh[:k]


def centred_inputs(H: torch.Tensor, meta: list[dict], fit: torch.Tensor) -> dict[str, torch.Tensor]:
    """{centre: [n, d] float64 input to the lens}. ``fit``: bool [n], the J++ fitting split."""
    out = {c: torch.empty_like(H) for c in CENTRES}
    out["none"] = H.clone()
    evals = sorted({m["eval"] for m in meta})
    tok = torch.tensor([m["read_token_id"] for m in meta])
    for ev in evals:
        rows = torch.tensor([m["eval"] == ev for m in meta])
        idx = rows.nonzero().squeeze(1)
        Ht = H[idx]
        n = len(idx)
        out["loo"][idx] = Ht - (Ht.sum(0, keepdim=True) - Ht) / (n - 1)
        fidx = (rows & fit).nonzero().squeeze(1)
        Hf = H[fidx]
        mu = Hf.mean(0)
        out["ref"][idx] = Ht - mu
        for j, i in enumerate(idx.tolist()):
            same = fidx[tok[fidx] == tok[i]]
            out["reftok"][i] = Ht[j] - (H[same].mean(0) if len(same) >= TOK_MIN else mu)
        Q = principal_directions(Hf, min(N_DIR, len(fidx) - 1))
        X = Ht - mu
        out["refpco4"][idx] = X - (X @ Q.T) @ Q
    return out


def ranks_for(logits: torch.Tensor, pair_item: torch.Tensor, pair_cands: torch.Tensor) -> torch.Tensor:
    """Their ``min_rank_over_candidates`` vectorised: 1 + #ids strictly above the best candidate.
    pair_cands [P, C] padded with -1."""
    L = logits[pair_item]  # [P, V]
    c = pair_cands.clamp_min(0)
    best = L.gather(1, c).masked_fill(pair_cands < 0, float("-inf")).max(1).values
    return (L > best[:, None]).sum(1) + 1


def score(args, model) -> None:
    import pandas as pd
    from lens_evals.readout_evals.readout_eval_items import (
        filter_items_by_correctness,
        load_readout_eval_items,
        non_semantic_token_ids,
        split_fitting_items,
    )
    from lens_evals.readout_evals.readout_eval_scoring import pass_at_k_over_layers
    from lens_evals.readout_evals.readout_evals import ReadoutResiduals
    from workspace_lens.utils import get_unembed_matrix

    dev = args.device
    res = ReadoutResiduals.load(args.out / "residuals.pt")
    meta = json.loads((args.out / "items.json").read_text())
    assert [(m["eval"], m["item"]) for m in meta] == res.item_keys
    items = {(it.eval_slug, it.name): it for it in load_items(args.jpp_repo)}
    kept = [items[k] for k in res.item_keys]  # scoreable, input order
    correct = filter_items_by_correctness(
        kept, hf_model_name=MODEL, correctness_csv=str(args.jpp_repo / "data/jlens/evaluations/model_correctness.csv")
    )
    fit_items, held_items = split_fitting_items(correct, seed=SPLIT_SEED, fit_fraction=FIT_FRACTION)
    key_of = lambda it: (it.eval_slug, it.name)  # noqa: E731
    fit_keys, held_keys, ok_keys = {key_of(i) for i in fit_items}, {key_of(i) for i in held_items}, {key_of(i) for i in correct}
    fit = torch.tensor([k in fit_keys for k in res.item_keys])
    for m in meta:
        k = (m["eval"], m["item"])
        m["split"] = "fit" if k in fit_keys else "held" if k in held_keys else "incorrect"
    (args.out / "items.json").write_text(json.dumps(meta, indent=1))

    W = get_unembed_matrix(model).float().to(dev)  # [V, d]
    V = W.shape[0]
    excl = torch.zeros(V, dtype=torch.bool, device=dev)
    excl[non_semantic_token_ids(model.tokenizer, vocab_size=V, items=load_readout_eval_items(str(args.jpp_repo / "data/jlens/evaluations")))] = True
    pairs = [(p, inter, c) for p, cands in enumerate(res.candidate_ids_P_list) for inter, c in cands.items()]
    C = max(len(c) for _p, _i, c in pairs)
    pair_item = torch.tensor([p for p, _i, _c in pairs], device=dev)
    pair_cands = torch.tensor([c + [-1] * (C - len(c)) for _p, _i, c in pairs], device=dev)
    layers = RECIPE_LAYERS if args.recipe_only else list(range(N_LAYERS))
    rows: list[dict] = []
    t0 = time.time()
    for lens in args.lenses:
        getJ = load_jacobian_getter(lens)
        for L in layers:
            H = res.residuals_L_dict_PN[L].double()
            X = centred_inputs(H, meta, fit)
            J = getJ(L).to(dev) if getJ else None
            denom = (torch.cat([(W[a : a + 16384] @ J).norm(dim=1) for a in range(0, V, 16384)]) if J is not None
                     else W.norm(dim=1)).clamp_min(1e-9)
            for c in CENTRES:
                Xc = X[c].float().to(dev)
                Z = Xc @ J.T if J is not None else Xc
                for ro in READOUTS:
                    logits = model.unembed(Z).float() if ro == "rms" else (Z @ W.T) / denom
                    for filt in (True, False):
                        lg = logits.masked_fill(excl, float("-inf")) if filt else logits
                        rk = ranks_for(lg, pair_item, pair_cands).tolist()
                        arm = f"{lens}|{c}|{ro}|{'filt' if filt else 'full'}"
                        rows += [{"eval": meta[p]["eval"], "lens": arm, "item": meta[p]["item"], "intermediate": i,
                                  "layer": L, "rank": r} for (p, i, _c), r in zip(pairs, rk, strict=True)]
            del J
            print(f"[score] {lens} L{L} {time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(args.out / "ranks.csv.gz", index=False)

    keys = lambda d, ks: d[[(e, i) in ks for e, i in zip(d["eval"], d["item"], strict=True)]]  # noqa: E731
    rec = df[df["layer"].isin(RECIPE_LAYERS)]
    summary = {}
    for split, ks in (("held", held_keys), ("all_correct", ok_keys), ("all", set(res.item_keys))):
        p = pass_at_k_over_layers(keys(rec, ks), KS)
        p.to_csv(args.out / f"pass_at_k-{split}.csv", index=False)
        summary[split] = {f"{r.lens}|{r.eval}|k{r.k}": round(float(r.pass_at_k), 4) for r in p.itertuples()}
    n = {s: len(k) for s, k in (("fit", fit_keys), ("held", held_keys), ("correct", ok_keys), ("scoreable", res.item_keys))}
    prov = Provenance(model=MODEL, model_revision=PINS[MODEL], reader="koayon/jpp-lenses", reader_revision=PINS["koayon/jpp-lenses"],
                      dataset=f"jpp_lens@{JPP_COMMIT}/data/jlens/evaluations (five MACRO_EVALS)", seed=SPLIT_SEED,
                      extra={"lenses": {k: (v, PINS[v[0]]) if v else None for k, v in LENSES.items()}, "centres": CENTRES,
                             "readouts": READOUTS, "layers_scored": layers, "recipe_layers": RECIPE_LAYERS, "fit_fraction": FIT_FRACTION,
                             "tok_min": TOK_MIN, "n_dir": N_DIR, "limit": args.limit, "n": n, "device": dev})
    write_artefact(args.out / "summary.json", prov, {"n": n, "pass_at_k": summary})
    held = pass_at_k_over_layers(keys(rec, held_keys), (10,))
    tab = held.pivot_table(index="lens", columns="eval", values="pass_at_k")
    print(tab.sort_values("macro", ascending=False).round(3).to_string(), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--jpp-repo", type=Path, required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--stages", default="capture,score")
    ap.add_argument("--lenses", default=",".join(LENSES))
    ap.add_argument("--limit", type=int, default=0, help="items per task (plumbing)")
    ap.add_argument("--recipe-only", action="store_true", help="score only the seven recipe layers")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    args.lenses = args.lenses.split(",")
    args.out = args.out or REPO_ROOT / "out" / ("jpp" + (f"-limit{args.limit}" if args.limit else ""))
    args.out.mkdir(parents=True, exist_ok=True)
    torch.set_grad_enabled(False)
    torch.backends.cuda.matmul.allow_tf32 = False
    jpp_imports(args.jpp_repo)
    from workspace_lens import get_hf_model

    model = get_hf_model(MODEL, attn_implementation="sdpa", revision=PINS[MODEL])
    stages = args.stages.split(",")
    if "capture" in stages:
        capture(args, model)
    if "score" in stages:
        score(args, model)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
