"""S15 diagnostic: where do the centres sit in J's spectrum? (notes/iteration-anthony/mu-log.md, card S15)

  python experiments/s15_spectrum.py --families typo,association,multihop --split fit [--ks 8,32,128,512]

For each family and layer: the share of ``||v||^2`` in the top-k right singular subspace of ``J_l`` for v = the family
mean (fam), the token means (tok), the read states h and h - fam, against the random expectation k / d. Needs only
the cached SVDs (``precompute_pullback.py --jsvd``) and the read-cell captures: no lens load. Writes
``out/analysis/S15/spectrum-<split>.{json,md}``.
"""

import argparse
import json

import torch

from jlm import OUT, geometry, pullback

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def share(V: torch.Tensor, Vh: torch.Tensor, k: int) -> float:
    """Mean over rows of ||P_k v||^2 / ||v||^2 with P_k the projection on the top-k right singular directions."""
    P = V @ Vh[:k].T
    return ((P**2).sum(1) / (V**2).sum(1).clamp_min(1e-12)).mean().item()


def gain(V: torch.Tensor, S: torch.Tensor, Vh: torch.Tensor) -> float:
    """Mean over rows of ||J v||^2 / ||v||^2, relative to a random direction's (mean of S^2): > 1 amplified."""
    P = V @ Vh.T
    return (((P**2) * S**2).sum(1) / (V**2).sum(1).clamp_min(1e-12)).mean().item() / (S**2).mean().item()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--split", default="fit")
    ap.add_argument("--ks", default="8,32,128,512")
    ap.add_argument("--drop-massive", type=int, default=0,
                    help="zero the m largest-|fam| coordinates (per family and layer) in every v first (S18: they hold "
                         "most of ||fam||^2 and none of its gain); outputs get a -m<m> suffix")
    args = ap.parse_args()
    ks = [int(k) for k in args.ks.split(",")]
    key = pullback.default_key()
    out, lines = {}, [f"# S15: share of ||v||^2 in J's top-k right singular subspace ({args.split}; random = k / d)", ""]
    for f in args.families.split(","):
        try:
            fam = geometry.fit(f, args.split, "fam", "self")
            tok = geometry.fit(f, args.split, "tok", "self")
        except FileNotFoundError as e:
            print(f"{f}: skipped ({e})")
            continue
        out[f] = {}
        lines += [f"## {f}", "", "| layer | v | " + " | ".join(f"k={k}" for k in ks) + " |", "|---|---|" + "---|" * len(ks)]
        for L in fam.layers:
            try:
                S, Vh = pullback.load_jsvd(key, L)
            except FileNotFoundError as e:
                print(e)
                return
            _, H, MU = fam.layer(L)
            _, _, MT = tok.layer(L)
            vs = {"fam": MU[:1], "tok": MT, "h": H, "h - fam": H - MU}
            if args.drop_massive:
                idx = MU[0].abs().topk(args.drop_massive).indices
                vs = {n: v.clone().index_fill_(1, idx, 0.0) for n, v in vs.items()}
            out[f][L] = {name: {k: share(v, Vh, k) for k in ks} for name, v in vs.items()}
            out[f][L]["gain"] = {name: gain(v, S, Vh) for name, v in vs.items()}
            out[f][L]["energy of J in top-k"] = {k: ((S[:k] ** 2).sum() / (S**2).sum()).item() for k in ks}
            out[f][L]["random"] = {k: k / Vh.shape[0] for k in ks}
            for name, row in out[f][L].items():
                if name == "gain":
                    continue
                lines.append(f"| {L} | {name} | " + " | ".join(f"{row[k]:.3f}" for k in ks) + " |")
        lines.append("")
        lines += [f"gain ||J v||^2 / ||v||^2 relative to a random direction ({f}):", "",
                  "| layer | " + " | ".join(out[f][fam.layers[0]]["gain"]) + " |", "|---|" + "---|" * 4]
        for L in fam.layers:
            lines.append(f"| {L} | " + " | ".join(f"{x:.2f}" for x in out[f][L]["gain"].values()) + " |")
        lines.append("")
    sfx = f"-m{args.drop_massive}" if args.drop_massive else ""
    root = OUT / "analysis" / "S15"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"spectrum-{args.split}{sfx}.json").write_text(json.dumps(out, indent=1))
    (root / f"spectrum-{args.split}{sfx}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
