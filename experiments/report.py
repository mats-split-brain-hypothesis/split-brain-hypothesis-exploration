"""One table across families: strict pass per arm (and judged pass where a judge run exists).

  python experiments/report.py --split val --arms "zero|cos,fam@fit|cos,tok@fit|cos"
  python experiments/report.py --split bench

Reads ``out/eval/<family>/<split>/summary.json`` (experiments/evaluate.py) and, per arm, every
``judged-*/results.json`` (experiments/judge.py). Strict is ours, not WorkspaceBench scores, and
is not a usable proxy on user_modeling or directed_modulation (notes/eval-pipeline.md); judged
numbers are labelled with the judge directory (model, layer subset). Writes ``out/eval/report-<split>.md``.
"""

import argparse
import json
from pathlib import Path

from evaluate import parse_arm, slug

from jlm import OUT

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]  # *_mt: free score = piece proxy
STRICT_IS_PROXY = {"typo", "association", "basic_readout", "multihop", "multilingual"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--split", default="val")
    ap.add_argument("--arms", default="")
    ap.add_argument("--out", default=str(OUT / "eval"))
    args = ap.parse_args()
    root = Path(args.out)
    sums = {f: json.loads(p.read_text())["result"] for f in FAMILIES if (p := root / f / args.split / "summary.json").exists()}
    arms = args.arms.split(",") if args.arms else sorted({a for s in sums.values() for a in s["arms"]})
    lines = [f"# {args.split}: strict pass (ours) per family and arm", "",
             "| family | n | strict is a proxy | " + " | ".join(arms) + " |",
             "|---|---|---|" + "---|" * len(arms)]
    judged = []
    for f, s in sums.items():
        cells = []
        for a in arms:
            r = s["arms"].get(a)
            cells.append(f"{r['strict']['value']:.2f}" if r else "")
            d = root / f / args.split / slug(parse_arm(a))
            runs = sorted(d.glob("judged*/results.json")) if d.exists() else []
            for res in [r for r in runs if "limit" not in r.parent.name]:  # smoke runs are not results
                j = json.loads(res.read_text())
                judged.append(f"| {f} | {a} | {res.parent.name} | {j['n_items']} | {j['numbers']['value']:.2f} |")
        proxy = "piece proxy" if f.endswith("_mt") else ("yes" if f in STRICT_IS_PROXY else "no")
        lines.append(f"| {f} | {s['n_scored']} | {proxy} | " + " | ".join(cells) + " |")
    if judged:
        lines += ["", ("## Judged (smoke runs omitted). `judged-claude-haiku-5.5*` = Haiku 5.5, the DEVELOPMENT judge "
                       "(unpinned, not WorkspaceBench scores); `judged` = the bench's pinned judge"), "",
                  "| family | arm | judge run | n | pass |", "|---|---|---|---|---|", *judged]
    text = "\n".join(lines) + "\n"
    (root / f"report-{args.split}.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
