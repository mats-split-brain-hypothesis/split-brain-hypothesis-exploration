"""Fill the readout-geometry caches the round-2 centres read (S13, S14, S15): one load of ``W_U`` and ``J``.

  python experiments/precompute_pullback.py --eig                                  # the per-layer pseudo-inverses (cached)
  python experiments/precompute_pullback.py --priors unigram-norobots,unigram-wikitext --ranks full,256
  python experiments/precompute_pullback.py --template-tokens template --ks 16,64,128
  python experiments/precompute_pullback.py --jsvd
  python experiments/precompute_pullback.py --next-token typo/fit,typo/val          # needs out/ctx (pod)
  python experiments/precompute_pullback.py --next-token all

Needs about 7 GB (``W_U`` fp32 and 12 layers of ``J``): the Mac under ``mac.lock`` with nothing else running, or a pod.
Outputs (``jlm.pullback``): ``out/lens/pb-eig-*``, ``wu-gram-*``, ``tbasis-*``, ``jsvd-*`` (lens caches, keyed by the pin);
``out/priors/pullback/<prior>-<readout>-r<rank>.pt`` (one ``g`` per layer, with its fit quality and decoded top tokens);
``out/priors/pullback/nt-<family>-<split>-<readout>-r<rank>.pt`` (per-cell pullbacks of the model's own next-token
log-softmax at the bank's read cells, from the context capture's layer 63). ``summary.md`` beside them.
"""

import argparse
import json
import time

import torch
from umot.provenance import PINS, Provenance, write_artefact

from jlm import OUT, REPO_ROOT, banks, capture, context
from jlm.lens import MODEL, Lens, reader
from jlm.pullback import (
    PULLBACK,
    Geometry,
    cells_path,
    centre_scores,
    prior_path,
    tbasis_path,
)

GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]
FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
TOP = 15


def _rank(r: str) -> str | int:
    return "full" if r == "full" else int(r)


def _prov(extra: dict) -> Provenance:
    return Provenance(model=MODEL, model_revision=PINS[MODEL], reader=reader("jlens")[0], reader_revision=reader("jlens")[1],
                      dataset="jlm/priors", extra=extra)


def do_priors(geo: Geometry, lens: Lens, names: list[str], readouts: list[str], ranks: list, ridge: float, log: list[str]) -> None:
    for name in names:
        src = OUT / "priors" / f"{name}.pt"
        obj = torch.load(src, weights_only=False)
        c = obj["logp"].float().unsqueeze(0)  # [1, V]
        if c.shape[1] != lens.vocab:
            raise ValueError(f"{src}: prior over {c.shape[1]} tokens, lens has {lens.vocab}")
        for readout in readouts:
            t = time.time()
            out = {rank: ({}, {"prior": name, "readout": readout, "rank": rank, "ridge": ridge, "source": obj.get("meta", {}),
                               "fit_quality": {}, "norm": {}, "decoded": {}}) for rank in ranks}
            for L in lens.layers:
                B = geo.rhs(centre_scores(c), L, readout)  # one pass over W_U, shared by every rank
                for rank, (layers, meta) in out.items():
                    g = geo.solve(B, L, readout, ridge=ridge, rank=None if rank == "full" else rank)
                    layers[L] = g[0].clone()
                    meta["fit_quality"][L] = round(geo.fit_quality(c, g, L, readout)[0].item(), 4)
                    meta["norm"][L] = round(g[0].norm().item(), 3)
                    meta["decoded"][L] = lens.display(lens.scores(g, L, readout).topk(TOP, dim=1).indices[0].tolist())
            for rank, (layers, meta) in out.items():
                path = prior_path(name, readout, rank)
                path.parent.mkdir(parents=True, exist_ok=True)
                torch.save({"layers": layers, "meta": meta}, path)
                write_artefact(path.with_suffix(".provenance.json"), _prov(meta), {"layers": sorted(layers)})
                fq = " ".join(f"L{L}:{q:.2f}" for L, q in meta["fit_quality"].items())
                log.append(f"- `{path.name}`: fit quality (||L(g) - c|| / ||c||) {fq}; L(g) at L44: "
                           f"{meta['decoded'].get(44, meta['decoded'][lens.layers[0]])}")
                print(f"{path.name} ({time.time() - t:.0f}s): {fq}", flush=True)


def do_template(geo: Geometry, lens: Lens, token_set: str, readouts: list[str], ks: list[int], log: list[str]) -> None:
    src = REPO_ROOT / "data" / "template_tokens" / f"{token_set}.json"
    spec = json.loads(src.read_text())
    ids = [e["id"] for e in spec["tokens"]]
    for k in ks:
        if k > len(ids):
            print(f"template set {token_set} has {len(ids)} tokens < k = {k}; skipped")
            continue
        for readout in readouts:
            for L in lens.layers:
                path = tbasis_path(geo.key, readout, token_set, k, L)
                if path.exists():
                    continue
                B = geo.reading_basis(ids[:k], L, readout)
                torch.save(B, path)
        log.append(f"- template basis `{token_set}` k={k}: {len(ids)} tokens available, bases at {sorted(lens.layers)} "
                   f"({', '.join(readouts)}); first tokens {[e['text'] for e in spec['tokens'][:8]]}")
        print(f"template bases k={k} done", flush=True)


def do_jsvd(geo: Geometry, lens: Lens, log: list[str]) -> None:
    for L in lens.layers:
        t = time.time()
        S, _ = geo.jsvd(L)
        share = (S[:32] ** 2).sum() / (S**2).sum()
        log.append(f"- J SVD L{L}: s1 {S[0]:.3g}, s32 {S[31]:.3g}, s_min {S[-1]:.3g}; top-32 energy share {share:.3f}")
        print(f"jsvd L{L} ({time.time() - t:.0f}s): top-32 share {share:.3f}", flush=True)


def do_next_token(geo: Geometry, lens: Lens, names: list[str], readouts: list[str], ranks: list, ridge: float, log: list[str]) -> None:
    for n in names:
        family, split = n.split("/")
        try:
            bank = banks.load(family, split)
            items = capture.load(bank)
            ctx = context.ContextStore.of(bank)
        except FileNotFoundError as e:
            print(f"{n}: skipped ({e})", flush=True)
            continue
        cells = [(it.id, i) for it in items for i in range(len(it.positions))]
        t = time.time()
        H = torch.stack([ctx.at(iid, context.FINAL_LAYER, i).float() for iid, i in cells])
        for readout in readouts:
            out = {rank: {L: torch.empty(len(cells), geo.d, dtype=torch.bfloat16) for L in lens.layers} for rank in ranks}
            quality = {rank: {L: [] for L in lens.layers} for rank in ranks}
            for a in range(0, len(cells), 128):
                C = centre_scores(torch.log_softmax(lens.logits(H[a : a + 128]), dim=1).cpu())
                for L in lens.layers:
                    B = geo.rhs(C, L, readout)  # shared by every rank
                    for rank in ranks:
                        g = geo.solve(B, L, readout, ridge=ridge, rank=None if rank == "full" else rank)
                        out[rank][L][a : a + 128] = g.to(torch.bfloat16)
                        quality[rank][L].append(geo.fit_quality(C, g, L, readout))
            for rank in ranks:
                meta = {"family": family, "split": split, "readout": readout, "rank": rank, "ridge": ridge,
                        "fit_quality": {L: round(torch.cat(q).mean().item(), 4) for L, q in quality[rank].items()},
                        "ctx": str(context.bank_path(bank).relative_to(OUT))}
                path = cells_path(family, split, readout, rank)
                path.parent.mkdir(parents=True, exist_ok=True)
                torch.save({"cells": cells, "layers": out[rank], "meta": meta}, path)
                write_artefact(path.with_suffix(".provenance.json"), _prov(meta), {"cells": len(cells)})
                log.append(f"- `{path.name}`: {len(cells)} cells; mean fit quality "
                           + " ".join(f"L{L}:{q:.2f}" for L, q in meta["fit_quality"].items()))
        print(f"{n}: {len(cells)} cells ({time.time() - t:.0f}s)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--layers", default="grid", help="comma-separated, or 'grid' (the 12 read layers)")
    ap.add_argument("--readouts", default="cos,rms")
    ap.add_argument("--ranks", default="full", help="pullback eigen-ranks, e.g. full,256")
    ap.add_argument("--ridge", type=float, default=1e-4, help="relative ridge (x mean eigenvalue)")
    ap.add_argument("--eig", action="store_true", help="only build the per-layer eigendecompositions")
    ap.add_argument("--priors", default="", help="comma-separated out/priors/<name>.pt stems")
    ap.add_argument("--template-tokens", default="", help="token set name under data/template_tokens")
    ap.add_argument("--ks", default="16,64,128")
    ap.add_argument("--jsvd", action="store_true")
    ap.add_argument("--next-token", default="", help="family/split,... or 'all' (needs out/ctx)")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    layers = GRID if args.layers == "grid" else [int(x) for x in args.layers.split(",")]
    readouts, ranks = args.readouts.split(","), [_rank(r) for r in args.ranks.split(",")]
    t0 = time.time()
    lens = Lens(layers, args.device, "jlens")
    geo = Geometry(lens)
    print(f"lens loaded ({time.time() - t0:.0f}s): V {lens.vocab}, d {geo.d}, key {geo.key}", flush=True)
    log = [f"# precompute_pullback ({time.strftime('%Y-%m-%d %H:%M')}): layers {layers}, readouts {readouts}, ranks {ranks}, ridge {args.ridge}", ""]
    if args.eig or args.priors or args.next_token:
        for readout in readouts:
            for L in layers:
                t = time.time()
                lam, _ = geo.eig(L, readout)
                print(f"eig {readout} L{L} ({time.time() - t:.0f}s): lam1 {lam[0]:.3g}, lam256 {lam[255]:.3g}, lam_min {lam[-1]:.3g}", flush=True)
                log.append(f"- A_l eigenvalues {readout} L{L}: lam1 {lam[0]:.3g}, lam256 {lam[255]:.3g}, lam_min {lam[-1]:.3g}")
    if args.priors:
        do_priors(geo, lens, args.priors.split(","), readouts, ranks, args.ridge, log)
    if args.template_tokens:
        do_template(geo, lens, args.template_tokens, readouts, [int(k) for k in args.ks.split(",")], log)
    if args.jsvd:
        do_jsvd(geo, lens, log)
    if args.next_token:
        names = ([f"{f}/{s}" for f in FAMILIES for s in ("fit", "val")] if args.next_token == "all" else args.next_token.split(","))
        do_next_token(geo, lens, names, readouts, ranks, args.ridge, log)
    PULLBACK.mkdir(parents=True, exist_ok=True)
    summary = PULLBACK / "summary.md"
    with summary.open("a") as f:
        f.write("\n".join(log) + "\n\n")
    print(f"done ({time.time() - t0:.0f}s); appended to {summary}")


if __name__ == "__main__":
    main()
