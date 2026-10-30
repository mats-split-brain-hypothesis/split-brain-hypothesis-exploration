"""Build the write-up's appendix table from the verified map rows, and insert it at APPENDIX_TABLE.

Usage: python3 src/writeup_appendix.py <ov_map.json> <writeup.md> [--published-only]
The 'Bears on' column is agent 9's interpretation; everything else is copied from the map.
--published-only skips map rows that have no BEARS_ON entry yet (rows added after the write-up's cut, which belong in
its next dated update) instead of stopping.
"""
import json
import sys

PUBLISHED_ONLY = "--published-only" in sys.argv
sys.argv = [a for a in sys.argv if a != "--published-only"]

BEARS_ON = {
    "1a": "4; 1a (metric is also an instruction); 2 (probe)", "1b": "4; 1a", "1c": "check that the measures move",
    "1d": "check that the measures move", "1e": "1a", "1f": "1a", "1m": "4 (score vs instruction)",
    "1q": "4", "1n": "4", "1o": "3; 4", "1g": "1a (doesn't test: both versions graded)", "1h": "3",
    "1i": "3", "1j": "3", "1k": "4; 1b (doesn't test: every voice reads as a test)", "1p": "4; 2 (decision-point probe)", "1l": "4",
    "1r": "3", "2p": "1a; 1b; 2", "2a": "2", "2b": "2", "2m": "2", "2c": "2", "2d": "method (harness)",
    "2e": "3 (hesitation)", "2g": "2", "2i": "1a; 3", "2j": "3 (persistence); 1b; 4 (person's-number follow-up)", "2k": "2", "2l": "2",
    "2n": "2 (realness check)", "2o": "1b", "2q": "1b; 3", "2r": "1a", "2s": "2; method",
    "3a": "1b", "3b": "1a (stakes)", "3c": "1a (harness cues)", "3e": "3 (persistence)", "3f": "1a", "3g": "1a; 1b (floor, doesn't test them)",
    "2t": "2 (realness check); method", "3h": "1a; 2; 3 (floor on the primary)",
}


def cell(text, limit=None):
    t = " ".join(str(text).split()).replace("|", "/")
    if limit and len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + " …"
    return t


rows = json.load(open(sys.argv[1]))
missing = [r["id"] for r in rows if r["id"] not in BEARS_ON]
extra = [k for k in BEARS_ON if k not in {r["id"] for r in rows}]
if extra or (missing and not PUBLISHED_ONLY):
    sys.exit(f"mapping mismatch: missing {missing}, extra {extra}")
if missing:
    print(f"skipping rows not yet in the write-up: {missing}")
    rows = [r for r in rows if r["id"] in BEARS_ON]

lines = [
    "One row per verified map row, in the map's order. Cue, behaviour, strength and source are copied from",
    "`ov_map.json` (cue shortened where marked …); the full result text is in the map. *Bears on* is agent 9's",
    "interpretation.",
    "",
    "| Row | Map tier | Cue | Behaviour | Bears on | Strength (map) | Source |",
    "|---|---|---|---|---|---|---|",
]
for r in rows:
    lines.append("| " + " | ".join([
        r["id"], cell(r["tier"]), cell(r["feature"], 160), cell(r["behaviour"], 100), BEARS_ON[r["id"]],
        cell(r["strength"], 140), cell(r["source"]),
    ]) + " |")
table = "\n".join(lines)

p = sys.argv[2]
s = open(p).read()
start = s.index("## Appendix: every result, its subclaim and source")
end = s.index("## Changelog")
s = s[:start] + "## Appendix: every result, its subclaim and source\n\n" + table + "\n\n" + s[end:]
open(p, "w").write(s)
print(f"{len(rows)} rows written")
