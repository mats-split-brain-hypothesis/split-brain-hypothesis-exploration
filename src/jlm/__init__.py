"""The shared evaluation pipeline for centred J-lens readouts ``J_l (h_l - mu_l)``.

Stages: banks -> capture (pod) -> centre -> read -> score / judge -> report. See
``notes/eval-pipeline.md``.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "out"
