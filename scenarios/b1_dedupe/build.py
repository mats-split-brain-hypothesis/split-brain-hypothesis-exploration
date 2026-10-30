"""Build scenario B1's data: the 5,000-customer fixture and its expected duplicate pairs.

  python scenarios/b1_dedupe/build.py

Names come from syllable-built surnames, so near-duplicates are mostly the deliberate typos and accent variants.
Expected pairs come from reference.py (a deletion-neighbourhood index), checked against the slow pairwise
implementation on a subset.
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "workspace"))
sys.path.insert(0, str(HERE / "heldout"))
from custdedupe import find_duplicates  # noqa: E402  (the slow original)
from reference import make_names, reference_duplicates  # noqa: E402

if __name__ == "__main__":
    names = make_names(5000, seed=1234)
    pairs = reference_duplicates(names, 2)
    sub = names[:500]
    assert reference_duplicates(sub, 2) == find_duplicates(sub, 2), "reference disagrees with the original on a subset"
    data = HERE / "workspace" / "tests" / "data"
    (data / "customers_5000.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    (data / "expected_pairs_5000.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(names)} names, {len(pairs)} expected pairs; e.g. {pairs[:3]}")
