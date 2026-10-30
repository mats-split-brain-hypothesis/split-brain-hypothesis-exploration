"""S24c: for every val2 flip (fam fails, arm passes; strict), the cell and layer where the arm passes, fam's top 50
there (fam = the mean of fit's read cells at the layer, as fam@fit), fam's rank of the target, and the arm's top 10.
Offline from captures + stored readouts; one lens load. Writes out/analysis/S24/flips.json for classification
(concept already in fam's top 50 in another form / script; near-miss form; absent).

  python experiments/s24c_dump.py --device cuda
"""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import parse_arm, read_jsonl, slug

from jlm import OUT, banks, capture, score
from jlm.lens import Lens

ARMS = {"S14b-x": "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos",
        "S14b": "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos",
        "S20x": "s20xt:1@fit|cos", "s20xon": "s20xon:1:kmx64@fit|cos"}
GRID = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--split", default="val2")
    ap.add_argument("--families", default="typo,association,multihop")
    ap.add_argument("--ref", default="fam", choices=["fam", "zero"], help="the reference whose failures and top 50 define a flip")
    ap.add_argument("--arms", default="", help="name=arm,... (default: the four S24c arms)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    arms = dict(a.split("=", 1) for a in args.arms.split(",")) if args.arms else ARMS
    lens = Lens(GRID, args.device)
    out = []
    for fam in args.families.split(","):
        bank = banks.load(fam, args.split)
        items = {it.id: it for it in capture.load(bank)}
        fit_items = capture.load(banks.load(fam, "fit"))
        mu = {L: torch.cat([it.acts[L].float() for it in fit_items]).mean(0) for L in GRID}
        if args.ref == "zero":
            mu = {L: torch.zeros_like(v) for L, v in mu.items()}
        root = OUT / "eval" / fam / args.split
        ref_arm = "fam@fit|cos" if args.ref == "fam" else "zero|cos"
        fam_pass = score.strict_items(read_jsonl(root / slug(parse_arm(ref_arm)) / "readouts.jsonl"), bank)
        meta = {it["id"]: it for it in bank.items}
        for name, arm in arms.items():
            d = root / slug(parse_arm(arm))
            p = score.strict_items(read_jsonl(d / "readouts.jsonl"), bank)
            rows = read_jsonl(d / "readouts.jsonl")
            ranks = read_jsonl(d / "ranks.jsonl")
            for iid in [i for i in p if p[i] and not fam_pass.get(i)]:
                hit = min((r for r in ranks if r["id"] == iid), key=lambda r: r["rank"])
                L, pos = hit["layer"], hit["pos"]
                it = items[iid]
                k = it.positions.index(pos)
                h = it.acts[L][k].float()
                s = lens.scores((h - mu[L])[None], L, "cos")[0].cpu()
                top = s.topk(50).indices.tolist()
                arm_top = next(r["tokens"] for r in rows if r["id"] == iid and r["layer"] == L and r["pos"] == pos)
                out.append({"family": fam, "item": iid, "arm": name, "layer": L, "pos": pos, "read_token": it.token(k),
                            "prompt": meta[iid].get("prompt"), "targets": meta[iid].get("intermediates"),
                            "target_display": lens.display([hit["best_id"]])[0],
                            "fam_rank_of_target": int((s > s[hit["best_id"]]).sum()),
                            "fam_top50": lens.display(top), "arm_top10": arm_top})
        print(f"{fam}: {sum(1 for o in out if o['family'] == fam)} flips", flush=True)
    dest = OUT / "analysis" / "S24"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"flips-{args.split}{args.tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
