"""S6 deep dive: where in depth the bridge entity and the answer appear on the multihop banks, under each centre,
and what the family mean does to them (notes/iteration-anthony/studies/S6.md).

  python experiments/s6_bridge.py --device cuda [--splits fit,val] [--arms zero,fam,rand.fam,xl4,...]

For every read cell, layer and arm (cos readout; g fitted on fit, own group excluded): the best rank of the bridge's
pieces (``intermediates``) and of the answer's pieces (target and alternatives), a piece being a single-token form or
a distinctive piece of a multi-token one (>= 4 characters, not a prompt token; ``jlm.mtproxy``'s rule with 4 for 3). And, per
layer, where the bridge and answer pieces sit in the decoded family mean ``L(mu)``: their z-score over the vocabulary
(high = subtracting mu pushes them down). Analysis looks at targets; no centre does.
Writes ``out/analysis/S6/extra/bridge-<family>-<split>.json`` and ``bridge.md``.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from jlm import OUT, banks, capture, centres
from jlm.centres import Batch, apply, cell_refs
from jlm.lens import Lens

FAMILIES = ["multihop", "multihop_mt"]
MIN_PIECE = 4  # stricter than the piece proxy (3): "ary", "und", "ile" are too generic to trace


def pieces(forms: list[str], prompt: str, tok, display) -> list[int]:
    in_prompt = {t.strip().casefold() for t in display(tok(prompt, add_special_tokens=False)["input_ids"])}
    out: set[int] = set()
    for f in forms:
        for v in (f, " " + f):
            ids = tok(v, add_special_tokens=False)["input_ids"]
            if len(ids) == 1:
                out.add(ids[0])
                continue
            out |= {t for t, n in zip(ids, display(ids), strict=True)
                    if n.strip().casefold() not in in_prompt and len(n.strip()) >= MIN_PIECE}
    return sorted(out)


def roles(item: dict, tok, display) -> dict[str, list[int]]:
    bridge = [f for u in item.get("units", []) if u["role"].startswith("bridge") for fs in u["forms"].values() for f in fs]
    bridge = bridge or list(item.get("intermediates", []))
    answer = [item["target"], *item.get("target_alts", [])]
    return {"bridge": pieces(bridge, item["prompt"], tok, display), "answer": pieces(answer, item["prompt"], tok, display)}


def best_rank(S: torch.Tensor, ids: list[int]) -> list[int]:
    if not ids:
        return [-1] * len(S)
    best = S[:, ids].max(1).values
    return (S > best[:, None]).sum(1).tolist()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--splits", default="fit,val")
    ap.add_argument("--arms", default="zero,fam,rand.fam,fam50,pmu,pco4,xl4,xlf4")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    out = OUT / "analysis" / "S6" / "extra"
    out.mkdir(parents=True, exist_ok=True)
    first = banks.load(FAMILIES[0], "fit")
    layers = banks.specs(first)[0].layers
    lens = Lens(layers, args.device)
    md = ["# S6: bridge and answer by layer (cos readout, g fitted on fit)", ""]
    for family in FAMILIES:
        fit_items = capture.load(banks.load(family, "fit"))
        for split in args.splits.split(","):
            bank = banks.load(family, split)
            items = capture.load(bank)
            by_id = {it.id: it for it in items}
            meta = bank.by_id()
            R = {i: roles(meta[i], lens.tokenizer, lens.display) for i in by_id}
            res = {"family": family, "split": split, "layers": layers, "roles": {i: {k: lens.display(v) for k, v in r.items()}
                                                                                     for i, r in R.items()},
                   "ranks": {}, "mu_z": {}}
            for name in args.arms.split(","):
                c = centres.make(name)
                c.fit(fit_items if split != "fit" else items, family)
                rk = {}
                for L in layers:
                    cells = cell_refs([it for it in items if L in it.acts], family, L)
                    H = torch.stack([by_id[x.item].acts[L][x.i].float() for x in cells])
                    S = lens.scores(apply(c, Batch(L, cells, H, by_id)), L, "cos")
                    for role in ("bridge", "answer"):
                        r = []
                        for j, x in enumerate(cells):
                            r.append(best_rank(S[j : j + 1], R[x.item][role])[0])
                        for x, v in zip(cells, r, strict=True):
                            key = (x.item, role)
                            rk.setdefault(key, {}).setdefault(L, v if v >= 0 else None)
                            if v >= 0 and (rk[key][L] is None or v < rk[key][L]):
                                rk[key][L] = v
                res["ranks"][name] = {f"{i}|{role}": v for (i, role), v in rk.items()}
            # where the bridge / answer sit in L(mu_fam): z over the vocabulary, per item and layer
            fam = centres.make("fam")
            fam.fit(fit_items if split != "fit" else items, family)
            for L in layers:
                cells = cell_refs(items, family, L)
                M = torch.stack([fam(x) for x in cells])
                S = lens.scores(M, L, "cos")
                Z = (S - S.mean(1, keepdim=True)) / S.std(1, keepdim=True)
                res["mu_z"][L] = {role: [float(Z[j, R[x.item][role]].max()) if R[x.item][role] else None
                                         for j, x in enumerate(cells)] for role in ("bridge", "answer")}
                g = torch.Generator().manual_seed(L)  # control: the max over as many random vocabulary ids
                res["mu_z"][L]["random"] = [
                    float(Z[j, torch.randint(lens.vocab, (max(1, len(R[x.item]["bridge"])),), generator=g)].max())
                    for j, x in enumerate(cells)]
            (out / f"bridge-{family}-{split}.json").write_text(json.dumps(res))
            md += summarise(res, args.arms.split(","))
            print("\n".join(md[-40:]), flush=True)
    (out / "bridge.md").write_text("\n".join(md) + "\n")


def summarise(res: dict, arms: list[str]) -> list[str]:
    L = res["layers"]
    lines = [f"## {res['family']}/{res['split']}", "",
             "Share of items with the role's best piece in the top 10, per layer (median rank in brackets at L40, L52, L60).",
             "", "| arm | role | " + " | ".join(f"L{x}" for x in L) + " | any layer | med L40/52/60 |",
             "|---|---|" + "---|" * (len(L) + 2)]
    for a in arms:
        R = res["ranks"][a]
        for role in ("bridge", "answer"):
            rows = [v for k, v in R.items() if k.endswith("|" + role) and any(x is not None for x in v.values())]
            if not rows:
                continue
            share = [np.mean([r[x] is not None and r[x] < 10 for r in rows]) for x in L]
            anyl = np.mean([any(v is not None and v < 10 for v in r.values()) for r in rows])
            med = [int(np.median([r[x] for r in rows if r[x] is not None])) for x in (40, 52, 60)]
            lines.append(f"| {a} | {role} | " + " | ".join(f"{s:.2f}" for s in share) + f" | {anyl:.2f} | {med} |")
    lines += ["", "z-score of the role's best piece in L(mu_fam) over the vocabulary (mean over items; high = fam pushes it "
              "down):", "", "| role | " + " | ".join(f"L{x}" for x in L) + " |", "|---|" + "---|" * len(L)]
    for role in ("bridge", "answer", "random"):
        zs = [np.mean([z for z in res["mu_z"][x][role] if z is not None]) for x in L]
        lines.append(f"| {role} | " + " | ".join(f"{z:+.2f}" for z in zs) + " |")
    return lines + [""]


if __name__ == "__main__":
    main()
