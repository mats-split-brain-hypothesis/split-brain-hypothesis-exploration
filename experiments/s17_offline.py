"""S17 offline preview: depth schedules scored from two arms' stored ranks (no lens load).

An item passes the schedule ``A up to L_s, B above`` when some cell has a target rank < 10 under A at a layer <= L_s or
under B above it (the rank-based pass the dashboard's per-layer curves use; on single-token families it is strict's
accepted-token test on target ids, on the _mt families the piece proxy's ranks). Checked against each arm's own
summary value (the full-schedule ends). Writes out/analysis/S17/offline-<split>.md.

  python experiments/s17_offline.py --split fit --a "fam@self|cos" --b "zero|cos"
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from jlm import OUT
from jlm.mu.clusters import FAMILIES

EVAL = OUT / "eval"


def arm_dir(arm: str) -> str:
    return arm.replace("|", "__").replace("@", "-at-").replace(":", "~")


def best(path: Path) -> dict:
    out = defaultdict(lambda: 10**9)
    for line in path.open():
        r = json.loads(line)
        if r.get("rank") is not None and r["rank"] >= 0:
            out[r["id"], r["layer"]] = min(out[r["id"], r["layer"]], r["rank"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="fit")
    ap.add_argument("--a", default="fam@self|cos")
    ap.add_argument("--b", default="zero|cos")
    ap.add_argument("--splits", default="36,40,44,48,52,56")
    args = ap.parse_args()
    Ls = [int(x) for x in args.splits.split(",")]
    lines = [f"Schedules {args.a} up to L_s, {args.b} above; rank-based pass@10 on {args.split}; columns = L_s, "
             f"then the two plain arms (rank-based / summary).", "",
             "| family | n | " + " | ".join(f"L{L}" for L in Ls) + " | swapped L48 | A | B | A summ. | B summ. |",
             "|---|---|" + "---|" * (len(Ls) + 5)]
    macro = defaultdict(list)
    for f in FAMILIES:
        root = EVAL / f / args.split
        summ = json.loads((root / "summary.json").read_text())["result"]
        ids = summ["scored_ids"]
        pa, pb = root / arm_dir(args.a) / "ranks.jsonl", root / arm_dir(args.b) / "ranks.jsonl"
        if not (pa.exists() and pb.exists()):
            lines.append(f"| {f} | missing ranks |")
            continue
        A, B = best(pa), best(pb)
        layers = sorted({L for (_, L) in A})

        def rate(split, first, second):
            return sum(any((first if L <= split else second)[i, L] < 10 for L in layers) for i in ids) / len(ids)

        row = [rate(L, A, B) for L in Ls] + [rate(48, B, A), rate(99, A, B), rate(-1, A, B)]
        for k, v in zip([*Ls, "sw48", "A", "B"], row, strict=True):
            macro[k].append(v)
        sa = summ["arms"].get(args.a, {}).get("strict", {}).get("value")
        sb = summ["arms"].get(args.b, {}).get("strict", {}).get("value")
        lines.append(f"| {f} | {len(ids)} | " + " | ".join(f"{v:.3f}" for v in row)
                     + f" | {sa if sa is None else round(sa, 3)} | {sb if sb is None else round(sb, 3)} |")
    lines.append("| **macro** | | " + " | ".join(f"{sum(v) / len(v):.3f}" for v in macro.values()) + " | | |")
    out = OUT / "analysis" / "S17"
    out.mkdir(parents=True, exist_ok=True)
    name = f"offline-{args.split}-{arm_dir(args.a)}+{arm_dir(args.b)}.md"
    (out / name).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
