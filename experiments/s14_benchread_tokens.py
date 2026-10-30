"""S14r token sets from the uncentred lens's readouts on the fit read cells (mu-log, card S14r).

The ``template`` set took the tokens shared by the decoded *family means* plus a hand list and frequent chat tokens;
this one takes the tokens the uncentred cos readout (``zero|cos``) puts in its top 10 at the fit read cells, counted
per family, kept when at least ``--min-families`` families share them, ordered by the number of families then by
count. No hand list, no means; fit / val targets excluded (``build_priors.target_ids``). Reads the stored readouts
(``out/eval/<family>/fit/zero__cos/readouts.jsonl``): runs on the Mac in seconds.

  python experiments/s14_benchread_tokens.py [--min-families 3] [--top 256]
  python experiments/s14_benchread_tokens.py --arm fam-at-self__cos --name famread        # S14f: fam's answer frame
  python experiments/s14_benchread_tokens.py --arm fam-at-self__cos --name tplframe --prepend template

Writes ``data/template_tokens/benchread.json``; bases from ``precompute_pullback.py --template-tokens benchread`` (pod).
"""

import argparse
import json
from collections import Counter, defaultdict

from build_priors import TEMPLATE_DIR, target_ids, tokenizer, vocab_display
from umot.provenance import PINS

from jlm import OUT
from jlm.lens import MODEL

FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation",
            "typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--min-families", type=int, default=3)
    ap.add_argument("--top", type=int, default=256)
    ap.add_argument("--name", default="benchread")
    ap.add_argument("--arm", default="zero__cos", help="whose fit readouts to count (S14f: fam-at-self__cos, the answer frame)")
    ap.add_argument("--prepend", default="", help="a token set whose first --prepend-k tokens go first (S14f: template)")
    ap.add_argument("--prepend-k", type=int, default=64)
    args = ap.parse_args()
    vocab = vocab_display(tokenizer())
    ids_of: dict[str, int] = {}
    for i, s in enumerate(vocab):
        ids_of.setdefault(s, i)
    excluded = target_ids(vocab)
    count, fams = Counter(), defaultdict(set)
    for f in FAMILIES:
        for line in (OUT / "eval" / f / "fit" / args.arm / "readouts.jsonl").open():
            for t in json.loads(line)["tokens"]:
                i = ids_of.get(t)
                if i is not None and i not in excluded:
                    count[i] += 1
                    fams[i].add(f)
    keep = [i for i in count if len(fams[i]) >= args.min_families]
    keep.sort(key=lambda i: (-len(fams[i]), -count[i]))
    if args.prepend:
        head = [t["id"] for t in json.loads((TEMPLATE_DIR / f"{args.prepend}.json").read_text())["tokens"]][: args.prepend_k]
        keep = head + [i for i in keep if i not in set(head)]
    toks = [{"id": i, "text": vocab[i], "sources": [f"{args.arm} top-10 on fit cells of {len(fams[i])} families, {count[i]} times"
                                                     if i in count else f"{args.prepend}[:{args.prepend_k}]"]}
            for i in keep[: args.top]]
    path = TEMPLATE_DIR / f"{args.name}.json"
    path.write_text(json.dumps({"name": args.name, "model": MODEL, "model_revision": PINS[MODEL], "n": len(toks),
                                "excluded_targets": len(excluded), "min_families": args.min_families,
                                "source": f"{args.arm} top-10 at the fit read cells" + (f", after {args.prepend}[:{args.prepend_k}]" if args.prepend else ""), "tokens": toks},
                               indent=1, ensure_ascii=False) + "\n")
    print(f"{path}: {len(toks)} of {len(keep)} shared tokens; first 40: {[t['text'] for t in toks[:40]]}")


if __name__ == "__main__":
    main()
