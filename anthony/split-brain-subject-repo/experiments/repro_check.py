"""Check that the pipeline reproduces stored results: a fresh tree against a stored one.

  python experiments/repro_check.py [--fresh eval --stored screen-premerge] [--changed fam@fitall,...]

For each (family, split, arm) present in both trees (under out/), compares the per-item strict passes
and the per-cell top-10 tokens. Arm directories match across naming schemes (``genk:8`` or ``genk~8``).
Arms whose definition changed on purpose since the stored run go in ``--changed``: reported, not failed.
First use (2026-10-10): out/screen vs the x-runs in out/eval, with fitall / fitothers / dict:fam2+ changed
(DM had joined the 7-family bank). Second (2026-10-11, after the iteration merge): out/eval vs
out/screen-premerge, nothing changed on purpose.
"""

import argparse
import json
from pathlib import Path

from jlm import OUT, banks, score


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fresh", default="eval")
    ap.add_argument("--stored", default="screen-premerge")
    ap.add_argument("--changed", default="", help="arm heads (centre@ref) whose definition changed on purpose")
    args = ap.parse_args()
    FRESH, STORED = OUT / args.fresh, OUT / args.stored
    CHANGED = {a: "changed on purpose" for a in args.changed.split(",") if a}
    same, differ, changed = [], [], []
    for fam_dir in sorted(p for p in FRESH.iterdir() if p.is_dir()):
        for split_dir in sorted(p for p in fam_dir.iterdir() if p.is_dir()):
            bank = banks.load(fam_dir.name, split_dir.name)
            for arm_dir in sorted(p for p in split_dir.iterdir() if (p / "readouts.jsonl").exists()):
                stored = STORED / fam_dir.name / split_dir.name
                old = next((stored / n / "readouts.jsonl" for n in (arm_dir.name, arm_dir.name.replace("~", ":"))
                            if (stored / n / "readouts.jsonl").exists()), None)
                if old is None:
                    continue
                arm = arm_dir.name.replace("__", "|").replace("-at-", "@").replace("~", ":")
                new_r, old_r = rows(arm_dir / "readouts.jsonl"), rows(old)
                key = lambda r: (r["id"], r["layer"], r["pos"])  # noqa: E731
                tok_new = {key(r): r["tokens"] for r in new_r}
                tok_old = {key(r): r["tokens"] for r in old_r}
                cells_equal = sum(tok_new.get(k) == v for k, v in tok_old.items())
                p_new, p_old = score.strict_items(new_r, bank), score.strict_items(old_r, bank)
                items_equal = sum(p_new[i] == p_old[i] for i in p_old)
                tag = f"{bank.name} {arm}: items {items_equal}/{len(p_old)}, top-10 cells {cells_equal}/{len(tok_old)}"
                base = arm.split("|")[0]
                if base in CHANGED:
                    changed.append(f"{tag}  [{CHANGED[base]}]")
                elif items_equal == len(p_old) and cells_equal == len(tok_old):
                    same.append(tag)
                else:
                    differ.append(tag)
    print(f"IDENTICAL ({len(same)}):", *same, sep="\n  ")
    print(f"\nDIFFER ({len(differ)}):", *differ, sep="\n  ")
    print(f"\nCHANGED ON PURPOSE ({len(changed)}):", *changed, sep="\n  ")


if __name__ == "__main__":
    main()
