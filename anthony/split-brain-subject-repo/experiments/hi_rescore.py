"""Re-score stored readouts of the hidden-intermediate families with ``jlm.intermediates`` (no lens, no forward pass).

  python experiments/hi_rescore.py                       # every arm under out/eval/{chain,brew}_intermediates/*
  python experiments/hi_rescore.py --families chain_intermediates --splits val,bench

Writes ``out/eval/<family>/<split>/hi_scores.json`` ({arm: extras, plus each arm's item passes}) and prints one table
per bank: headline pass, the matched null (other items' intermediates), lift with a paired item-bootstrap 95 %
interval, and the near-miss / start / answer diagnostics. Prompt tokens (the digit rule) come from re-rendering the
bank with the bench's planner, not from the captures.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer
from wsbench.produce.render import display_tokens, render

from jlm import OUT, banks, intermediates, score
from jlm.lens import MODEL

N_BOOT = 10_000


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def lift_ci(S: intermediates.Scorer, rows: list[dict], ids: list[str]) -> list[float]:
    """Paired item bootstrap of pass - null: per item, its pass minus its mean hit rate over the derangements."""
    p = S.passes(rows)
    head = S.headline(rows)
    hits = [S._hits(head, tab) for tab in S._derangements()]
    d = []
    for i in ids:
        scored = [h[i] for h, tab in zip(hits, S._derangements(), strict=True) if tab[i]]
        d.append(float(p[i]) - (float(np.mean(scored)) if scored else 0.0))
    d = np.array(d)
    boot = d[np.random.default_rng(score.SEED).integers(0, len(d), (N_BOOT, len(d)))].mean(1)
    return [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", default=",".join(intermediates.FAMILIES))
    ap.add_argument("--splits", default="fit,val,bench")
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(MODEL)
    disp = lambda ids: display_tokens(tok, ids)  # noqa: E731
    for fam in args.families.split(","):
        for split in args.splits.split(","):
            bank = banks.load(fam, split)
            root = OUT / "eval" / fam / split
            prompt_ids = {s.id: render(s, tok).ids for s in banks.specs(bank)}
            S = intermediates.Scorer(bank, tok, disp, prompt_ids)
            ids = [i for i, why in S.conf.items() if not why]
            out = {"bank": bank.name, "n_items": len(bank.items), "n_scored": len(ids), "arms": {}}
            for d in sorted(p for p in root.iterdir() if (p / "readouts.jsonl").exists()):
                arm = json.loads((d / "provenance.json").read_text())["provenance"]["extra"].get("arm", d.name) \
                    if (d / "provenance.json").exists() else d.name
                rows = read_jsonl(d / "readouts.jsonl")
                ex = S.extras(rows, ids)
                ex["lift_ci95"] = lift_ci(S, rows, ids)
                ex["passes"] = {i: S.passes(rows)[i] for i in ids}
                out["arms"][arm] = ex
            (root / "hi_scores.json").write_text(json.dumps(out, indent=1) + "\n")
            print(f"\n{bank.name}: n scored {len(ids)} / {len(bank.items)}")
            keys = ["pass", "null", "lift", "near", "start", "answer"] + (["stir_region"] if fam.startswith("brew") else [])
            print(f"{'arm':<70} " + " ".join(f"{k:>7}" for k in keys) + "  lift 95%")
            for a, ex in out["arms"].items():
                print(f"{a[:70]:<70} " + " ".join(f"{ex[k]:>7.3f}" if ex.get(k) is not None else f"{'-':>7}" for k in keys)
                      + f"  [{ex['lift_ci95'][0]:+.3f}, {ex['lift_ci95'][1]:+.3f}]")


if __name__ == "__main__":
    main()
