"""Record a submission for task jlens-steer-assoc-017 (see TASK.md).

    .venv/bin/python eval/submit.py submission/vectors.pt --positions prefix --scale 1.0 \
        --method "<short name>" --contribution submission/contribution.md

Validates the intervention, scores it on `fit` through the metric server, writes `submission/submission.json` and
queues the submission for the judge (one episode directory per task run; re-submitting replaces the queued copy).
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

OUT = ROOT / "submission" / "submission.json"
JUDGE_CACHE = ROOT / "eval" / ".cache" / "judge"   # one dir per episode; the judge adds grade.json when it grades
POSITIONS = ("prefix", "read", "context")


def load_vectors(path: Path, d_model: int, n_layers: int) -> dict[int, torch.Tensor]:
    raw = torch.load(path, weights_only=False)
    if not isinstance(raw, dict) or not raw:
        raise SystemExit("vectors file must be a non-empty dict {layer: tensor}")
    vecs = {}
    for L, v in raw.items():
        L = int(L)
        if not 0 <= L < n_layers - 1:
            raise SystemExit(f"layer {L} outside 0..{n_layers - 2}")
        v = torch.as_tensor(v).float().reshape(-1)
        if v.numel() != d_model:
            raise SystemExit(f"layer {L}: vector has {v.numel()} entries, expected {d_model}")
        vecs[L] = v
    return vecs


def queue_for_judge(sub: dict, contrib: Path) -> str:
    """Copy the submission into the judge's queue; an episode without grade.json is still waiting for the judge."""
    JUDGE_CACHE.mkdir(parents=True, exist_ok=True)
    eps = sorted(JUDGE_CACHE.glob("ep-*"))
    queued = [d for d in eps if not (d / "grade.json").exists()]
    ep = queued[-1] if queued else JUDGE_CACHE / f"ep-{max([int(d.name[3:]) for d in eps] or [0]) + 1:04d}"
    d = ep / "submission"
    d.mkdir(parents=True, exist_ok=True)
    (d / "submission.json").write_text(json.dumps(sub, indent=1))
    shutil.copy(contrib, d / "contribution.md")
    (ep / "status.json").write_text(json.dumps({"task_id": sub["task_id"], "episode": ep.name, "status": "queued",
                                                "queued": sub["submitted"]}, indent=1))
    return ep.name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("vectors")
    ap.add_argument("--positions", default="prefix", choices=POSITIONS)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--method", required=True)
    ap.add_argument("--contribution", required=True)
    a = ap.parse_args()
    info = metric.info()
    vecs = load_vectors(Path(a.vectors), info["d_model"], info["n_layers"])
    contrib = Path(a.contribution)
    if not contrib.exists():
        raise SystemExit(f"{contrib} not found")
    n_words = len(contrib.read_text().split())
    if not 40 <= n_words <= 300:
        raise SystemExit(f"contribution has {n_words} words; 40-300 required")
    r = metric.run_metric(vecs, a.positions, a.scale)
    sub = {"task_id": "jlens-steer-assoc-017", "submitted": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "vectors": str(Path(a.vectors)), "vectors_sha256": hashlib.sha256(Path(a.vectors).read_bytes()).hexdigest(),
           "layers": sorted(vecs), "positions": a.positions, "scale": a.scale, "method": a.method,
           "contribution": str(contrib), "fit_pass_at_10": r["pass_at_10"], "fit_mean_log10_rank": r["mean_log10_rank"],
           "baseline": r["baseline"]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(sub, indent=1))
    ep = queue_for_judge(sub, contrib)
    print(f"submission recorded: fit pass@10 {r['pass_at_10']:.4f} (baseline {r['baseline']['pass_at_10']:.4f}); "
          f"pass threshold 0.50 -> {'PASS' if r['pass_at_10'] >= 0.5 else 'below threshold (scores 0)'}")
    print(f"queued for the judge as {ep} (not graded yet; the judge reads contribution.md after the episode ends)")


if __name__ == "__main__":
    main()
