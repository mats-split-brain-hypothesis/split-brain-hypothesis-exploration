"""The _mt families' piece-proxy pass split by scored unit, for any arms (val by default): S4's study_S4_units.py
with the arms and the output as arguments (instance e1; A's script left as it is).

  python experiments/e1_units.py --arms "fam@fit|cos,s14t64@fit|cos" --out out/analysis/S20x/mt-units-xcheck
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import study_S4_units as base  # noqa: E402

from jlm import OUT  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--out", required=True, help="path stem, e.g. out/analysis/S20x/mt-units")
    args = ap.parse_args()
    base.ARMS = [a.replace("|", "__").replace("@", "-at-").replace(":", "~") for a in args.arms.split(",")]
    d = OUT / "analysis" / "S4" / "extra"
    keep = {p: p.read_text() for p in d.glob("mt-units.*")}  # base writes here: restore A's files afterwards
    try:
        base.main()
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        for suf in ("json", "md"):
            out.with_suffix(f".{suf}").write_text((d / f"mt-units.{suf}").read_text())
    finally:
        for p, t in keep.items():
            p.write_text(t)


if __name__ == "__main__":
    main()
