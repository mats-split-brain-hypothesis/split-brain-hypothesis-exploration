"""S16 neighbour-overlap diagnostic: how often a kNN centre's neighbours share the read cell's carrier.

For each read cell of a bank (default directed_modulation/val, pool = every family's fit read cells), the neighbours
an arm averages (``members``) are compared with the cell: "same carrier" = the neighbour's rendered context ends in the
same last ``n`` tokens as the cell's (S8 / S4's test: DM mid-sentence cells share their last 6 tokens with same-sentence
neighbours), "same token" = same read token. Base rate: the share of all pool rows that match. Reported per layer
and pooled, separately for sentence-final cells (read token ".") and mid-sentence cells.

  python experiments/s16_overlap.py --banks directed_modulation/val,multihop/val --arms knnx8,s16pc8,s16pcd8,s16pr8
Writes out/analysis/S16/overlap.{json,md}.
"""

import argparse
import json
from collections import defaultdict

import torch

from jlm import OUT, banks, capture, centres
from jlm.mu.clusters import FAMILIES

N_TAIL = 6


def pool_contexts() -> list[tuple[str, ...]]:
    """Each pool row's last N_TAIL context tokens, in ``Pool.bench_fit`` row order."""
    out = []
    for f in FAMILIES:
        for it in capture.load(banks.load(f, "fit")):
            for i in range(len(it.positions)):
                out.append(tuple(it.decoded[max(0, it.idx[i] + 1 - N_TAIL): it.idx[i] + 1]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--banks", default="directed_modulation/val")
    ap.add_argument("--arms", default="knnx8,s16pc8,s16pcd8,s16pr8")
    ap.add_argument("--layers", default="", help="comma list; default every layer of the bank")
    args = ap.parse_args()
    tails = pool_contexts()
    res = {}
    for spec in args.banks.split(","):
        fam, split = spec.split("/")
        bank = banks.load(fam, split)
        items = capture.load(bank)
        groups = {it["id"]: it.get("pair_id") or it["id"] for it in bank.items}
        layers = [int(x) for x in args.layers.split(",")] if args.layers else sorted(items[0].acts)
        for name in args.arms.split(","):
            c = centres.make(name)
            c.fit(items, fam, groups)
            toks = c.pool.toks
            acc = defaultdict(lambda: [0, 0, 0, 0])  # (kind) -> [same carrier, same token, neighbours, base carrier]
            for L in layers:
                cells = centres.cell_refs(items, fam, L, groups)
                H = torch.stack([next(it for it in items if it.id == cr.item).acts[L][cr.i].float() for cr in cells])
                batch = centres.Batch(L, cells, H, {it.id: it for it in items})
                for cr, rows in zip(cells, c.members(batch), strict=True):
                    tail = cr.context[-N_TAIL:]
                    kind = "final" if cr.token.strip() in (".", "?", "!") else "mid"
                    a = acc[kind]
                    for r in rows.tolist():
                        a[0] += tails[r] == tail
                        a[1] += toks[r] == cr.token
                        a[2] += 1
            base = defaultdict(lambda: [0, 0])
            for cr in centres.cell_refs(items, fam, layers[0], groups):
                kind = "final" if cr.token.strip() in (".", "?", "!") else "mid"
                tail = cr.context[-N_TAIL:]
                base[kind][0] += sum(t == tail for t in tails)
                base[kind][1] += len(tails)
            res[f"{spec}|{name}"] = {k: {"same_carrier": v[0] / max(v[2], 1), "same_token": v[1] / max(v[2], 1),
                                         "base_carrier": base[k][0] / max(base[k][1], 1), "neighbours": v[2]}
                                     for k, v in acc.items()}
            print(spec, name, json.dumps(res[f"{spec}|{name}"]), flush=True)
    out = OUT / "analysis" / "S16"
    out.mkdir(parents=True, exist_ok=True)
    (out / "overlap.json").write_text(json.dumps(res, indent=1))
    lines = ["| bank | arm | cells | same carrier | base rate | same read token |", "|---|---|---|---|---|---|"]
    for key, r in res.items():
        spec, name = key.split("|")
        for kind, v in sorted(r.items()):
            lines.append(f"| {spec} | {name} | {kind} | {v['same_carrier']:.3f} | {v['base_carrier']:.4f} | {v['same_token']:.3f} |")
    (out / "overlap.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
