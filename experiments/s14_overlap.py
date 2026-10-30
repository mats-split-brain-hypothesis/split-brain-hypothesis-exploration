"""S14 diagnostic: how much of fam, h and h - fam lies in the template reading subspace B_k (vs a random k-dim one).

  python experiments/s14_overlap.py [--split fit] [--ks 16,64,128] [--readout cos]

Share of ||v||^2 in span(B_k) per family and layer (random = k / d). Writes ``out/analysis/S14/overlap-<split>.md``.
Cached bases only (``out/lens/tbasis-*``); no lens load.
"""

import argparse

from jlm import OUT, geometry, pullback

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--split", default="fit")
    ap.add_argument("--ks", default="16,64,128")
    ap.add_argument("--readout", default="cos")
    args = ap.parse_args()
    ks = [int(k) for k in args.ks.split(",")]
    key = pullback.default_key()
    lines = [f"# S14: share of ||v||^2 in the template reading subspace B_k ({args.split}, {args.readout} bases)", ""]
    for f in FAMILIES:
        fam = geometry.fit(f, args.split, "fam", "self")
        lines += [f"## {f}", "", "| layer | v | " + " | ".join(f"k={k}" for k in ks) + " |", "|---|---|" + "---|" * len(ks)]
        for L in fam.layers:
            _, H, MU = fam.layer(L)
            vs = {"fam": MU[:1], "h": H, "h - fam": H - MU}
            Bs = {k: pullback.load_tbasis(key, args.readout, "template", k, L).float() for k in ks}
            for name, V in vs.items():
                row = [((V @ Bs[k]) ** 2).sum(1).div((V**2).sum(1)).mean().item() for k in ks]
                lines.append(f"| {L} | {name} | " + " | ".join(f"{x:.3f}" for x in row) + " |")
            lines.append(f"| {L} | random | " + " | ".join(f"{k / H.shape[1]:.3f}" for k in ks) + " |")
        lines.append("")
    root = OUT / "analysis" / "S14"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"overlap-{args.split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
