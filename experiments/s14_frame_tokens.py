"""S14f: per-family "answer frame" token sets (mechanism probe, uses the family label like fam; never targets).

For each family F: the tokens in fam@self|cos's top 10 on at least ``--share`` of F's fit read cells (counted per item),
fit / val targets excluded, ordered by that share. Pooled across families, fam's readouts share answer *categories*
(ocean, animals, cities, countries), not the frame; the frame (">Name", "called", "known", "implies") is per family.
Writes ``data/template_tokens/frame-<family>.json`` (bases: ``precompute_pullback.py --template-tokens frame-<family>``).

  python experiments/s14_frame_tokens.py [--share 0.15] [--top 64]
"""

import argparse
import json
from collections import Counter

from build_priors import TEMPLATE_DIR, target_ids, tokenizer, vocab_display
from umot.provenance import PINS

from jlm import OUT
from jlm.lens import MODEL

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--share", type=float, default=0.15)
    ap.add_argument("--top", type=int, default=64)
    args = ap.parse_args()
    vocab = vocab_display(tokenizer())
    ids_of: dict[str, int] = {}
    for i, s in enumerate(vocab):
        ids_of.setdefault(s, i)
    excluded = target_ids(vocab)
    for f in FAMILIES:
        per_item: dict[str, set] = {}
        for line in (OUT / "eval" / f / "fit" / "fam-at-self__cos" / "readouts.jsonl").open():
            r = json.loads(line)
            per_item.setdefault(r["id"], set()).update(ids_of[t] for t in r["tokens"] if t in ids_of)
        n = len(per_item)
        c = Counter(i for s in per_item.values() for i in s if i not in excluded)
        keep = [i for i, k in c.most_common() if k / n >= args.share][: args.top]
        toks = [{"id": i, "text": vocab[i], "sources": [f"fam top-10 on {c[i]} / {n} {f} fit items"]} for i in keep]
        (TEMPLATE_DIR / f"frame-{f}.json").write_text(json.dumps(
            {"name": f"frame-{f}", "model": MODEL, "model_revision": PINS[MODEL], "n": len(toks), "excluded_targets": len(excluded),
             "share": args.share, "tokens": toks}, indent=1, ensure_ascii=False) + "\n")
        print(f"{f}: {len(toks)}; {[t['text'] for t in toks[:16]]}")


if __name__ == "__main__":
    main()
