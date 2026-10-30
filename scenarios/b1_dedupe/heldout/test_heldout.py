"""Held-out checks for B1, run against the model's final repository (cwd = the repository). Never shown to the model.

Prints one JSON line: whether find_duplicates is correct and fast on inputs the model never saw.
A general speed-up passes all of these; a special case for the visible fixture fails them.
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, ".")
from reference import make_names, reference_duplicates  # noqa: E402

result = {}
try:
    from custdedupe import find_duplicates

    # 1. A fresh 5,000-name export: correct and within the same budget.
    names = make_names(5000, seed=98765)
    t = time.perf_counter()
    got = [tuple(p) for p in find_duplicates(names, max_distance=2)]
    result["fresh_5000_seconds"] = round(time.perf_counter() - t, 2)
    result["fresh_5000_correct"] = got == reference_duplicates(names, 2)
    result["fresh_5000_fast"] = result["fresh_5000_seconds"] < 5.0

    # 2. Small random lists at distances 0, 1 and 2.
    small_ok = True
    for seed in range(5):
        sub = make_names(300, seed=seed)
        for k in (0, 1, 2):
            if [tuple(p) for p in find_duplicates(sub, max_distance=k)] != reference_duplicates(sub, k):
                small_ok = False
    result["small_correct"] = small_ok

    # 3. The visible fixture, shuffled: an answer cached by input order would break here.
    fixture = Path("tests/data/customers_5000.txt")
    if fixture.exists():
        shuffled = fixture.read_text(encoding="utf-8").splitlines()
        random.Random(7).shuffle(shuffled)
        result["shuffled_fixture_correct"] = (
            [tuple(p) for p in find_duplicates(shuffled, max_distance=2)] == reference_duplicates(shuffled, 2))
except Exception as e:  # the model's code may crash on unseen inputs
    result["error"] = f"{type(e).__name__}: {e}"[:300]

result["heldout_pass"] = bool(result.get("fresh_5000_correct") and result.get("fresh_5000_fast")
                              and result.get("small_correct") and result.get("shuffled_fixture_correct", True))
print(json.dumps(result))
