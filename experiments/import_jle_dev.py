"""Import jle's dev bank v2 (``jle/data/x90-dev/bank-v2``) as our dev banks.

Split A -> ``fit``, split B -> ``val``, written to ``data/dev/<family>/{fit,val}.json`` in the
bench's items.json format. Items flagged ``target_in_bench`` are dropped: a dev item may not
share a target with the bench (it would let a centre selected on dev see bench answers).
user_modeling is the exception: its targets are values of a closed attribute set (every Gender
item shares "male" / "female" with the bench), so overlapping items are kept; jle's filters
already ban reused bench prompts, which is the leak that matters there. Multihop items get the bench's ``readout`` field (``last_word_token``: the last non-whitespace
token of the prompt, jle's ``last_word_rule``), so the bench's planner reads them as it reads
the bench.

  python experiments/import_jle_dev.py --families typo
"""

import argparse
import json
from collections import Counter

from jlm import REPO_ROOT
from jlm.banks import DEV_ROOT
from jlm.lens import MODEL

#: jle now lives in its own checkout next to this repo.
SRC = REPO_ROOT.parent / "jlens-edits-1" / "data" / "x90-dev" / "bank-v2"
SPLIT = {"A": "fit", "B": "val"}
KEEP_TARGET_OVERLAP = {"user_modeling"}  # closed attribute values; see the module docstring


def last_word_readout(prompt: str, tokenizer) -> dict:
    from wsbench.produce.render import display_tokens

    tokens = display_tokens(tokenizer, tokenizer(prompt, add_special_tokens=False)["input_ids"])
    k = 1
    while k < len(tokens) and not tokens[-k].strip():
        k += 1
    return {"kind": "last_word_token", "offsets": [-k]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", required=True)
    args = ap.parse_args()
    manifest = json.loads((SRC / "manifest.json").read_text())
    for family in args.families.split(","):
        rows = [json.loads(line) for line in (SRC / f"{family}.jsonl").read_text().splitlines() if line]
        if family == "multihop":
            from transformers import AutoTokenizer
            from umot.provenance import PINS

            tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
            for r in rows:
                r["readout"] = last_word_readout(r["prompt"], tok)
            print(f"multihop readout offsets: {Counter(r['readout']['offsets'][0] for r in rows)}")
        drop = family not in KEEP_TARGET_OVERLAP
        dropped = Counter(r["split"] for r in rows if drop and r.get("target_in_bench"))
        for split, name in SPLIT.items():
            items = [r for r in rows if r["split"] == split and not (drop and r.get("target_in_bench"))]
            path = DEV_ROOT / family / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            header = {
                "family": family,
                "split": name,
                "source": f"jle/data/x90-dev/bank-v2/{family}.jsonl split {split} (jle git {manifest['git_sha'][:7]})",
                "gate": manifest["gate"],
                "dropped_target_in_bench": dropped[split],
            }
            path.write_text(json.dumps({**header, "items": items}, ensure_ascii=False, indent=1) + "\n")
            print(f"{family}/{name}: {len(items)} items ({dropped[split]} dropped: target in bench) -> {path}")


if __name__ == "__main__":
    main()
