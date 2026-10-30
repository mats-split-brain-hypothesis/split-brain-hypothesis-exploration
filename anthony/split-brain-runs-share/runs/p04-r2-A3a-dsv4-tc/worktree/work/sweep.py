"""Sweep positions x scales for a vectors file, printing pass@10 and mean log10 rank."""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric


def main():
    vectors_path, = sys.argv[1].split()
    raise SystemExit(0)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("vectors")
    ap.add_argument("--scales", default="1,2,3,4,5,6,8")
    ap.add_argument("--positions", default="read,prefix,context")
    a = ap.parse_args()
    vecs = {int(L): v for L, v in torch.load(a.vectors, weights_only=False).items()}
    print(f"layers {sorted(vecs)}  vectors {a.vectors}")
    for pos in a.positions.split(","):
        for s in [float(x) for x in a.scales.split(",")]:
            r = metric.run_metric(vecs, pos, s)
            print(f"pos={pos:7s} scale={s:4g}  pass@10={r['pass_at_10']:.4f}  "
                  f"log10rank={r['mean_log10_rank']:.3f}  ({r.get('elapsed_s', 0):.0f}s)")