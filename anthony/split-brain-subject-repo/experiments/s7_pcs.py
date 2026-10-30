"""S7 diagnosis: what the family's top principal directions hold (notes/iteration-anthony/studies/S7.md).

  python experiments/s7_pcs.py --device cuda [--k 16] [--split val]

Per family, with pco<k> fitted on fit (as the val arms are): at each grid layer, split every val read cell's centred
state x = h - mu into the removed part r = V V^T x and the kept part x - r, and report the median rank of the item's
target pieces (and, on multihop, of the final answer) in L(r) and in L(x - r): if r ranks the target high, removing the
PCs removes content. Also decodes each of the top 4 PCs (both signs) at L36 / L48 / L56 and their variance shares.
Analysis only (it reads targets); writes ``out/analysis/S7/extra/pcs.{json,md}``.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from s6_bridge import pieces  # noqa: E402

from jlm import OUT, banks, capture, centres  # noqa: E402
from jlm.centres import cell_refs  # noqa: E402
from jlm.lens import Lens  # noqa: E402

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def target_forms(item: dict) -> list[str]:
    units = [f for u in item.get("units", []) if u.get("required") for fs in u["forms"].values() for f in fs]
    if units:
        return units
    from jlm.banks import targets
    return targets(item)


def rank_of(S: torch.Tensor, ids: list[int]) -> int:
    best = S[ids].max()
    return int((S > best).sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--split", default="val")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    out = OUT / "analysis" / "S7" / "extra"
    out.mkdir(parents=True, exist_ok=True)
    layers = banks.specs(banks.load("typo", "fit"))[0].layers
    lens = Lens(layers, args.device)
    res, md = {}, [f"# S7: what the top {args.k} PCs hold (pco{args.k} fitted on fit, read on {args.split})", ""]
    md += ["Median rank of the target's pieces in the decoded removed part L(VV^T x) vs the kept part L(x - VV^T x), "
           "and the removed part's share of ||x||^2, per layer.", "",
           "| family | role | " + " | ".join(f"L{L}" for L in layers) + " |", "|---|---|" + "---|" * len(layers)]
    for fam in FAMILIES:
        c = centres.make(f"pco{args.k}")
        c.fit(capture.load(banks.load(fam, "fit")), fam)
        bank = banks.load(fam, args.split)
        items = capture.load(bank)
        meta = bank.by_id()
        tgt = {it.id: pieces(target_forms(meta[it.id]), meta[it.id].get("prompt", ""), lens.tokenizer, lens.display)
               for it in items}
        ans = {it.id: pieces([meta[it.id]["target"]], meta[it.id].get("prompt", ""), lens.tokenizer, lens.display)
               for it in items} if fam == "multihop" else None
        rows = {"removed": [], "kept": [], "share": []} | ({"answer removed": [], "answer kept": []} if ans else {})
        dec = {}
        for L in layers:
            cells = [x for x in cell_refs(items, fam, L) if tgt[x.item]]
            mu, V = c._basis(L, "\0none")
            X = torch.stack([next(it for it in items if it.id == x.item).acts[L][x.i].float() for x in cells]) - mu
            R = (X @ V) @ V.T
            Sr, Sk = lens.scores(R, L, "cos"), lens.scores(X - R, L, "cos")
            rows["removed"].append(int(np.median([rank_of(Sr[j], tgt[x.item]) for j, x in enumerate(cells)])))
            rows["kept"].append(int(np.median([rank_of(Sk[j], tgt[x.item]) for j, x in enumerate(cells)])))
            rows["share"].append(float((R.norm(dim=1) ** 2 / X.norm(dim=1) ** 2).mean()))
            if ans:
                ok = [j for j, x in enumerate(cells) if ans[x.item]]
                rows["answer removed"].append(int(np.median([rank_of(Sr[j], ans[cells[j].item]) for j in ok])))
                rows["answer kept"].append(int(np.median([rank_of(Sk[j], ans[cells[j].item]) for j in ok])))
            if L in (36, 48, 56):
                P = torch.cat([V[:, :4].T, -V[:, :4].T]) * X.norm(dim=1).mean()
                top = lens.scores(P, L, "cos").topk(8, dim=1).indices
                dec[L] = [lens.display(t.tolist()) for t in top]
        res[fam] = {"rows": rows, "decoded": {str(L): v for L, v in dec.items()}}
        for role, v in rows.items():
            fmtv = (lambda z: f"{z:.2f}") if role == "share" else str
            md.append(f"| {fam} | {role} | " + " | ".join(fmtv(z) for z in v) + " |")
        print("\n".join(md[-len(rows):]), flush=True)
    md += ["", "## Top 4 PCs decoded (+ then - direction), L48", ""]
    for fam, r in res.items():
        md.append(f"**{fam}**")
        for j, toks in enumerate(r["decoded"].get("48", [])):
            md.append(f"- PC{j % 4 + 1}{'+' if j < 4 else '-'}: {' '.join(repr(t) for t in toks)}")
        md.append("")
    (out / "pcs.json").write_text(json.dumps(res, ensure_ascii=False))
    (out / "pcs.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
