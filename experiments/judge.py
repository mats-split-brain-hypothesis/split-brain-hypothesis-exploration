"""Judge evaluated arms with the bench's judge prompts. Default judge: Haiku 5.5 (development, unpinned).

The default model is ``jlm.judge.DEV_JUDGE`` (``anthropic/claude-haiku-5.5``): a development judge,
not the bench's pinned one, so results are unpinned and never WorkspaceBench scores.
``--judge-model pinned`` uses the bench's own judge (Gemini 3.8 Flash, capped at 20 rpm on our account).

  python experiments/judge.py --family typo --split val --arms "zero|cos" --dry-run
  python experiments/judge.py --family typo --split val --arms "zero|cos" --limit 3
  python experiments/judge.py --family typo --split val --arms "zero|cos,fam@fit|cos"

Reads ``out/eval/<family>/<split>/<arm>/readouts.jsonl`` (from experiments/evaluate.py) and
writes the bench's ``results.json`` and verdict cache ``cells.jsonl`` to ``.../<arm>/judged``
(``judged-limitN`` for a smoke run). Cached verdicts are reused, so a rerun only pays for what
is missing. Keys: OPENROUTER_API_KEY in the environment or in umot/.env.
"""

import argparse
from pathlib import Path

from evaluate import parse_arm, slug

from jlm import OUT, banks, hfdata
from jlm.judge import DEV_JUDGE, judge


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--family", required=True)
    ap.add_argument("--split", required=True, choices=banks.SPLITS)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--judge-model", default=DEV_JUDGE,
                    help=f"default {DEV_JUDGE} (unpinned dev judge); 'pinned' for the bench's own judge")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--layers", default="", help="judge only these layers, e.g. 24,36,48,60 (result is then incomplete)")
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--rpm", type=float, default=1200, help="request pace (a new OpenRouter account allows 20 rpm per model)")
    ap.add_argument("--out", default=str(OUT / "eval"))
    args = ap.parse_args()
    bank = banks.load(args.family, args.split)
    for a in args.arms.split(","):
        d = Path(args.out) / bank.family / bank.split / slug(parse_arm(a))
        model = None if args.judge_model == "pinned" else args.judge_model
        tag = "judged" if model is None else f"judged-{model.split('/')[-1]}"
        layers = [int(x) for x in args.layers.split(",")] if args.layers else None
        if layers:
            tag += "-L" + "-".join(map(str, layers))
        out = d / (f"{tag}-limit{args.limit}" if args.limit else tag)
        r = judge(bank, d / "readouts.jsonl", out, judge_model=model, limit=args.limit, dry_run=args.dry_run, rpm=args.rpm, layers=layers, concurrency=args.concurrency)
        if not args.dry_run:
            spend = r.counts.get("spend_usd", 0.0) or 0.0
            print(f"{a}: {r.metric}={r.value} ci95={r.ci95} n={r.n_items} spend=${spend:.4f} "
                  f"pinned={r.pinned_instrument} complete={r.complete} -> {out}")
            hfdata.share([out])  # to the shared dataset (no-op if unset)


if __name__ == "__main__":
    main()
