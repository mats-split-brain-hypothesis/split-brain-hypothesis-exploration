"""Pick N tasks from ImpossibleBench's LiveCodeBench conflicting split by seeded draw, excluding given ids.

    python src/pick_tasks.py 20 20261022 lcbhard_58,lcbhard_99,lcbhard_27,lcbhard_63,lcbhard_101
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ib_variants import ib_variant  # noqa: E402

n, seed, exclude = int(sys.argv[1]), int(sys.argv[2]), set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
ids = sorted({str(s.id) for s in ib_variant(label="list").dataset} - exclude, key=lambda x: int(x.split("_")[1]))
pick = sorted(random.Random(seed).sample(ids, n), key=lambda x: int(x.split("_")[1]))
print(f"{len(ids)} eligible conflicting-split tasks; picked {n} (seed {seed}):")
print(",".join(pick))
