"""DM polarity selectivity: judged directed_modulation passes split by the prompt's polarity (xcheck-S16.md).

Every DM item mentions its concept X; only the ``think`` twins ask the model to hold it (``dont_think`` and
``suppress`` ask it not to). The uncentred lens passes think 11 / 26 and dont_think 0 / 26 on val: the model's state
separates them, so a centre that surfaces what the model holds keeps the contrast and a prompt reader surfaces X under
every polarity. Reads every judged DM run (``out/eval/directed_modulation/<split>/<arm>/judged-*/results.json``; pass =
gold picked and content-bound at any judged cell) and writes ``out/analysis/DM-polarity/<split>.md``.

  python experiments/dm_polarity.py [--split val]
"""

import argparse
import collections
import json

from jlm import OUT, banks

POLARITIES = ["think", "dont_think", "suppress"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--split", default="val")
    args = ap.parse_args()
    items = {it["id"] if "id" in it else it["name"]: it for it in banks.load("directed_modulation", args.split).items}
    pol = {i: it.get("polarity") for i, it in items.items()}
    n = collections.Counter(pol.values())
    root = OUT / "eval" / "directed_modulation" / args.split
    lines = [f"# DM polarity selectivity ({args.split}; Haiku judged; in brackets: items passing only at the sentence-final cell)", "",
             "| arm | judge run | " + " | ".join(f"{p} ({n[p]})" for p in POLARITIES) + " | total | think - dont_think "
             "| sentence-final-only share of passes |",
             "|---|---|" + "---|" * (len(POLARITIES) + 3)]
    rows = []
    for res in sorted(root.glob("*/judged-*/results.json")):
        if "limit" in res.parts[-2]:
            continue
        d = json.loads(res.read_text())
        last = collections.defaultdict(int)
        for r in d["rows"]:
            last[r["item"]] = max(last[r["item"]], r["pos"])
        ok, mid = set(), set()
        for r in d["rows"]:
            if r.get("pick") == "gold" and r.get("basis") == "content_bound":
                ok.add(r["item"])
                if r["pos"] != last[r["item"]]:
                    mid.add(r["item"])
        c = {p: (sum(1 for i in ok if pol.get(i) == p), sum(1 for i in ok - mid if pol.get(i) == p)) for p in POLARITIES}
        share = len(ok - mid) / len(ok) if ok else 0.0
        rows.append((c["think"][0] - c["dont_think"][0], res.parts[-3], res.parts[-2], c, len(ok) / len(items), share))
    for diff, arm, run, c, tot, share in sorted(rows, key=lambda r: (-r[0], r[1])):
        lines.append(f"| {arm} | {run.removeprefix('judged-')} | " + " | ".join(f"{c[p][0]} ({c[p][1]})" for p in POLARITIES)
                     + f" | {tot:.3f} | {diff:+d} | {share:.2f} |")
    out = OUT / "analysis" / "DM-polarity"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
