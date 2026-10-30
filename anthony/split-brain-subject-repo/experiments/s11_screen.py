"""Card S11: screen centres on the UM mention-control bank (notes/iteration-anthony/studies/S11.md).

Per centre, fitted within each condition (implies / mentions / absent; group = the source item), the best rank of the
item's strict targets (``jlm.score.accepted_ids``) over the read cells and grid layers, cos readout. Source items
whose target is unreachable or leaks into any variant's prompt (``jlm.score.confirmatory``) are dropped for all three.
Reports pass@10 and the median best rank per condition, over all cells, the request cells (before ``<|im_end|>``) and
the chat-template cells.

  python experiments/s11_screen.py --device cuda [--arms ...]  -> out/analysis/S11/{summary.json,summary.md}
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from s11_bank import load

from jlm import OUT, capture, centres, score
from jlm.lens import Lens

ARMS = "zero,fam,tok,u1rel,u1tokxs,u1endcar,u1carpos,shuf.u1rel,rand.u1rel"
SCOPES = ("all", "request", "template")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--arms", default=ARMS)
    ap.add_argument("--out", default=str(OUT / "analysis" / "S11"))
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    t0 = time.time()
    bank = load()
    meta = bank.by_id()
    items = capture.load(bank)
    layers = sorted({L for it in items for L in it.acts})
    lens = Lens(layers, args.device)
    vocab = lens.display(list(range(lens.vocab)))
    acc = score.accepted_ids(vocab, bank)
    conf = score.confirmatory(bank, acc, {it.id: lens.display(it.ids) for it in items})
    bad = {meta[i]["pair_id"] for i, why in conf.items() if why}
    items = [it for it in items if meta[it.id]["pair_id"] not in bad]
    groups = {it.id: meta[it.id]["pair_id"] for it in items}
    pools = defaultdict(list)
    for it in items:
        pools[meta[it.id]["condition"]].append(it)
    tmpl = {it.id: next((k for k, t in enumerate(it.idx) if it.decoded[t] == "<|im_end|>"), len(it.idx)) for it in items}
    print(f"{len(items)} items ({len(bad)} source items dropped: {sorted(bad)}), layers {layers} ({time.time() - t0:.0f}s)",
          flush=True)

    summary = {}
    for arm in args.arms.split(","):
        best = defaultdict(lambda: {s: 10**9 for s in SCOPES})
        for cond, pool in sorted(pools.items()):
            c = centres.make(arm)
            c.fit(pool, "user_modeling", groups)
            by = {it.id: it for it in pool}
            for L in layers:
                cells = centres.cell_refs(pool, "user_modeling", L, groups)
                H = torch.stack([by[x.item].acts[L][x.i].float() for x in cells])
                X = centres.apply(c, centres.Batch(L, cells, H, by, None))
                for a in range(0, len(cells), 512):
                    S, blk = lens.scores(X[a : a + 512], L, "cos"), cells[a : a + 512]
                    for j, x in enumerate(blk):
                        ids = acc[x.item]
                        if not ids:
                            continue
                        b = S[j, ids].max()
                        r = int((S[j] >= b).sum()) - 1  # pessimistic on ties
                        sc = "request" if x.i < tmpl[x.item] else "template"
                        for s in ("all", sc):
                            best[x.item][s] = min(best[x.item][s], r)
        res = {}
        for s in SCOPES:
            res[s] = {}
            for cond in sorted(pools):
                rs = [best[it.id][s] for it in pools[cond] if best[it.id][s] < 10**9]
                res[s][cond] = {"pass": float(np.mean([r < 10 for r in rs])) if rs else None,
                                "median_rank": float(np.median(rs)) if rs else None, "n": len(rs)}
        summary[arm] = res
        print(f"  {arm} ({time.time() - t0:.0f}s) " + json.dumps(res["all"]), flush=True)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({"arms": summary, "layers": layers, "dropped": sorted(bad)}, indent=1))
    conds = sorted(pools)
    lines = ["# S11 UM mention control: pass@10 (median best rank) of the item's strict target, per condition", "",
             "| arm | scope | " + " | ".join(conds) + " |", "|---|---|" + "---|" * len(conds)]
    for arm, res in summary.items():
        for s in SCOPES:
            lines.append(f"| {arm} | {s} | " + " | ".join(
                f"{res[s][c]['pass']:.2f} ({res[s][c]['median_rank']:.0f})" if res[s][c]["pass"] is not None else "-"
                for c in conds) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
