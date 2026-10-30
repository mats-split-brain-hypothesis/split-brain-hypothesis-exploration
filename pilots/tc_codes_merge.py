"""Merge the readers' per-run tables (pilots/tc-reading/<run>.codes.tsv, <run>.quotes.tsv; brief-tc.md item 14) into
pilots/tc-reading/codes.tsv and key_quotes.tsv for the dashboard. Each quote is checked against its block of the dump
(~/split-brain-run/dumps/<run>.txt, blocks as dump_reasoning.py numbers them): key_quotes.tsv gets a `verified`
column (exact | ws: matches after collapsing whitespace | elsewhere:<block>: found in another block | no).

    python3 tc_codes_merge.py
"""

import re
from pathlib import Path

R = Path(__file__).resolve().parent / "tc-reading"
DUMPS = Path.home() / "split-brain-run" / "dumps"
CODES = ["run", "outcome", "hack_level", "considered", "eval_aware", "design", "credit_track", "first_source_block", "status"]
QUOTES = ["run", "block", "kind", "quote", "label"]


def blocks(run: str) -> dict[int, str]:
    f = DUMPS / f"{run}.txt"
    out, cur = {}, None
    for line in (f.read_text().splitlines() if f.exists() else []):
        m = re.match(r"^\[(\d+)\] ", line)
        if m:
            cur = int(m.group(1)); out[cur] = ""
        elif cur is not None:
            out[cur] += line + "\n"
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    codes, quotes, bad = [], [], 0
    for f in sorted(R.glob("*.codes.tsv")):
        for line in f.read_text().splitlines():
            if line.strip() and not line.startswith("run\t"):
                codes.append((line.split("\t") + [""] * len(CODES))[: len(CODES)])
    cache = {}
    for f in sorted(R.glob("*.quotes.tsv")):
        for line in f.read_text().splitlines():
            if not line.strip() or line.startswith("run\t"):
                continue
            row = (line.split("\t") + [""] * len(QUOTES))[: len(QUOTES)]
            run, block, q = row[0], row[1], row[3].strip().strip('"')
            bl = cache.setdefault(run, blocks(run))
            b = int(re.sub(r"\D", "", block) or -1)
            text = bl.get(b, "")
            if q and q in text:
                v = "exact"
            elif q and norm(q) in norm(text):
                v = "ws"
            else:
                hit = next((k for k, t in bl.items() if q and norm(q) in norm(t)), None)
                v = f"elsewhere:{hit}" if hit is not None else "no"
            bad += not v.startswith(("exact", "ws"))
            quotes.append(row + [v])
    (R / "codes.tsv").write_text("\t".join(CODES) + "\n" + "".join("\t".join(r) + "\n" for r in codes))
    (R / "key_quotes.tsv").write_text("\t".join(QUOTES + ["verified"]) + "\n" + "".join("\t".join(r) + "\n" for r in quotes))
    print(f"{len(codes)} runs coded, {len(quotes)} quotes ({bad} not found in their block)")


if __name__ == "__main__":
    main()
