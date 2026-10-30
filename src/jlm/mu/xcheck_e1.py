"""Cross-check centres (instance e1, night-2): other k-means seeds for A's finalist ``sched:40:kmx64+s14t64`` (S14k).

``kmx64s<seed>``: S4's kmx64 (k-means of every family's fit read cells, k = 64, J++'s router space) with k-means++
seeded by ``seed`` instead of 0; everything else identical (``clusters.ClusterMean``). Seed 0 is ``kmx64``.
"""

from jlm.centres import CENTRES
from jlm.mu.clusters import ClusterMean

OWNER = "Anthony"
CANDIDATES = ()


def _seeded(k: int, seed: int) -> ClusterMean:
    c = ClusterMean(k, "bench", seed=seed)
    c.name = f"kmx{k}s{seed}"
    c.doc += f" [k-means++ seed {seed}]"
    return c


for _s in (1, 2):
    CENTRES[f"kmx64s{_s}"] = lambda s=_s: _seeded(64, s)
