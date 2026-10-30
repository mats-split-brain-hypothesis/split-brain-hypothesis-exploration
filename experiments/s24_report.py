"""S24 / S24b report: strict pass of the registered arms on a held-out split, per family, split by each item's
``fresh_target`` flag (written by s24_build: no accepted form among any bank's targets), with paired bootstrap
intervals against fam within family. Reads out/eval/<family>/<split>/; writes out/analysis/S24/<split>.md.

  python experiments/s24_report.py --split val2b --families multihop,multilingual
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import parse_arm, read_jsonl, slug

from jlm import OUT, banks, score

ARMS = ["zero|cos", "sched:40:kmx64+s14t64@fit|cos", "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos",
        "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5@fit|cos", "s20xt:1@fit|cos",
        "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos", "s14:template:64:mean=kmx64:a=0.5@fit|cos",
        "s20xon:1:kmx64@fit|cos"]
RMS = ["s14:template:64:mean=kmx64:a=0.5@fit|rms", "s20xonrms:1:kmx64@fit|rms"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val2b")
    ap.add_argument("--families", default="multihop,multilingual")
    args = ap.parse_args()
    lines = [f"# S24 report: {args.split} (strict; Δ vs fam with paired bootstrap 95 % per family; fresh / shared answers)", ""]
    for fam in args.families.split(","):
        bank = banks.load(fam, args.split)
        fresh = {it["id"]: it.get("fresh_target", True) and it.get("fresh_answer", True) for it in bank.items}  # headline: both
        S = json.loads((OUT / "eval" / fam / args.split / "summary.json").read_text())["result"]
        ids = S["scored_ids"]
        P = {}
        for a in ["fam@fit|cos", "fam@fit|rms"] + ARMS + RMS:
            p = OUT / "eval" / fam / args.split / slug(parse_arm(a)) / "readouts.jsonl"
            if not p.exists():
                continue
            P[a] = score.strict_items(read_jsonl(p), bank)
        groups = {"all": ids, "fresh": [i for i in ids if fresh.get(i, True)], "shared": [i for i in ids if not fresh.get(i, True)]}
        lines += [f"## {fam} (n all {len(groups['all'])}, fresh {len(groups['fresh'])}, shared {len(groups['shared'])})", "",
                  "| arm | all | Δ fam all [95 %] | fresh | Δ fam fresh | shared | Δ fam shared |", "|---|---|---|---|---|---|---|"]
        rng = random.Random(0)
        for a in ["fam@fit|cos"] + ARMS + ["fam@fit|rms"] + RMS:
            if a not in P:
                continue
            ref = "fam@fit|rms" if a.endswith("|rms") else "fam@fit|cos"
            row = [a]
            for g in ("all", "fresh", "shared"):
                L = groups[g]
                if not L:
                    row += ["–", "–"]
                    continue
                v = sum(P[a][i] for i in L) / len(L)
                d = v - sum(P[ref][i] for i in L) / len(L)
                cell = f"{d:+.3f}"
                if g == "all":
                    bs = sorted(sum(P[a][k] - P[ref][k] for k in (rng.choice(L) for _ in L)) / len(L) for _ in range(2000))
                    cell += f" [{bs[50]:+.3f}, {bs[1949]:+.3f}]"
                row += [f"{v:.3f}", cell]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    out = OUT / "analysis" / "S24"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
