"""Paired item-bootstrap differences between arms of different maps (``evaluate.py`` pairs arms within one map
only): per family, strict pass of ``a`` minus ``b`` over the scored items, 95 % interval; macro over families.

    python experiments/ll4_paired.py --split val --pairs "ll4w8:zero|cos=zero|cos,ll4w8f:fam@fit|cos=fam@fit|cos"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from evaluate import parse_arm, read_jsonl, slug  # noqa: E402

from jlm import OUT, banks, score  # noqa: E402

FAMILIES = banks.dev_families()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--pairs", required=True)
    a = ap.parse_args()
    out = {}
    for pair in a.pairs.split(","):
        x, y = pair.split("=")
        res = {}
        for f in FAMILIES:
            root = OUT / "eval" / f / a.split
            summ = json.loads((root / "summary.json").read_text())["result"]
            passes = {}
            for arm in (x, y):
                rows = read_jsonl(root / slug(parse_arm(arm)) / "readouts.jsonl")
                bank = banks.load(f, a.split)
                if f.endswith("_mt"):
                    from jlm import mtproxy
                    from jlm.lens import Lens  # noqa: F401  (tokenizer only below)
                    from transformers import AutoTokenizer
                    from umot.provenance import PINS
                    from wsbench.produce.render import display_tokens

                    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.6-27B", revision=PINS["Qwen/Qwen3.6-27B"])
                    units = mtproxy.units_of(bank, tok, lambda ids: display_tokens(tok, ids))
                    passes[arm] = mtproxy.item_passes(rows, units)
                    ids = [i for i, ok in mtproxy.reachable(units).items() if ok]
                else:
                    passes[arm] = score.strict_items(rows, bank)
                    ids = None
            if ids is None:  # the confirmatory items, as evaluate.py scores them
                ids = _scored(f, a.split)
            assert len(ids) == summ["arms"][y]["strict"]["n"], (f, len(ids), summ["arms"][y]["strict"]["n"])
            res[f] = score.paired(passes[x], passes[y], ids)
            print(f, pair, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[f].items()}, flush=True)
        d = [r["diff"] for r in res.values()]
        out[pair] = {"families": res, "macro_diff": sum(d) / len(d)}
        print("MACRO", pair, round(out[pair]["macro_diff"], 4), flush=True)
    (OUT / "analysis" / "LL4" / f"paired-{a.split}.json").write_text(json.dumps(out, indent=1))


def _scored(family: str, split: str) -> list[str]:
    """The confirmatory item ids (strict scorer's exclusions applied), as evaluate.py computes them."""
    from evaluate import scorers

    from jlm import capture
    from jlm.lens import Lens

    bank = banks.load(family, split)
    items = capture.load(bank)
    lens = _scored.lens = getattr(_scored, "lens", None) or Lens([40], "cpu")
    vocab = lens.display(list(range(lens.vocab)))
    sc, _ = scorers(bank, vocab, {it.id: lens.display(it.ids) for it in items})
    return [i for i, why in sc.conf.items() if not why]


if __name__ == "__main__":
    main()
