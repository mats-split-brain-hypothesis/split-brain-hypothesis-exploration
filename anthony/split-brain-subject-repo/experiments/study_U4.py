"""U4 cut 1: are J++'s wins the items the family mean also fixes? (notes/iteration-anthony/studies/U4.md)

  python experiments/study_U4.py --split val

Reads the battery (out/analysis/U4-<split>/<bank>.json, won / lost lists vs zero|cos) and the rank sidecars
(out/eval/<family>/<split>/<arm>/ranks.jsonl). Per family: the overlap of the items J++ fixes with those the family
mean fixes, and the Spearman correlation across items of their log rank gains over zero|cos. Analysis only: it looks
at targets through the stored ranks; no centre is built from it.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from jlm import OUT, score

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def best_rank(path: Path) -> dict[str, int]:
    return score.best_rank(json.loads(line) for line in path.read_text().splitlines())


def spearman(a, b) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1]) if len(a) > 2 else math.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--jpp", default="jpp:zero|cos")
    ap.add_argument("--centre", default="fam@fit|cos")
    args = ap.parse_args()
    bat = OUT / "analysis" / f"U4-{args.split}"
    out = OUT / "analysis" / "U4" / "extra"
    out.mkdir(parents=True, exist_ok=True)
    slug = lambda a: a.replace(":", "~").replace("@", "-at-").replace("|", "__")
    rows, report = [], {}
    for fam in FAMILIES:
        p = bat / f"{fam}-{args.split}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        arms = d["arms"]
        won = lambda a, ref: set(arms[a]["vs"][ref]["won"]) if ref in arms[a].get("vs", {}) else None
        J, F = won(args.jpp, "zero|cos"), won(args.centre, "zero|cos")
        if F is None:  # the battery stores refs' comparisons on the arm only; fall back to the ref's own vs
            F = set(arms[args.centre].get("vs", {}).get("zero|cos", {}).get("won", []))
        Jf = won(args.jpp, args.centre)  # items J++ passes and the family mean misses
        Fj = set(arms[args.jpp]["vs"][args.centre]["lost"])
        base = OUT / "eval" / fam / args.split
        rz, rj, rf = (best_rank(base / slug(a) / "ranks.jsonl") for a in ("zero|cos", args.jpp, args.centre))
        ids = sorted(set(rz) & set(rj) & set(rf))
        gj = np.array([math.log2((rz[i] + 1) / (rj[i] + 1)) for i in ids])
        gf = np.array([math.log2((rz[i] + 1) / (rf[i] + 1)) for i in ids])
        rep = {"n": d["n_scored"], "jpp_fixes": len(J), "fam_fixes": len(F), "both": len(J & F), "jpp_only": len(J - F),
               "fam_only": len(F - J), "jpp_beats_fam": sorted(Jf), "fam_beats_jpp": sorted(Fj),
               "rank_gain_spearman": spearman(gj, gf), "rank_gain_median": [float(np.median(gj)), float(np.median(gf))],
               "jpp_only_items": sorted(J - F), "fam_only_items": sorted(F - J)}
        report[fam] = rep
        rows.append(f"| {fam} | {rep['n']} | {len(J)} | {len(F)} | {len(J & F)} | {len(J - F)} | {len(F - J)} | "
                    f"{len(Jf)} / {len(Fj)} | {rep['rank_gain_spearman']:+.2f} | {gj.mean():+.2f} / {gf.mean():+.2f} |")
    (out / f"u4_overlap-{args.split}.json").write_text(json.dumps(report, indent=1))
    md = [f"# U4 cut 1 ({args.split}): {args.jpp} vs {args.centre}, each against zero|cos", "",
          "fixes = items passing under the arm and failing under zero|cos. Rank gain = log2 of best-rank ratio over zero "
          "(per item, ranks sidecar). J>F / F>J = items one passes and the other fails.", "",
          "| family | n | J++ fixes | fam fixes | both | J++ only | fam only | J>F / F>J | Spearman(rank gains) | mean gain J / F |",
          "|---|---|---|---|---|---|---|---|---|---|", *rows]
    (out / f"u4_overlap-{args.split}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
