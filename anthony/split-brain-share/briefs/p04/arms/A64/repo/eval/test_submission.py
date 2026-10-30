"""Submission checks (TASK.md). Run: .venv/bin/python -m pytest eval/test_submission.py -q"""

import json
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import metric  # noqa: E402

SUB = ROOT / "submission" / "submission.json"


@pytest.fixture(scope="module")
def sub() -> dict:
    assert SUB.exists(), "no submission: run eval/submit.py"
    return json.loads(SUB.read_text())


@pytest.fixture(scope="module")
def rerun(sub) -> dict:
    vecs = {int(L): v for L, v in torch.load(ROOT / sub["vectors"], weights_only=False).items()}
    return metric.run_metric(vecs, sub["positions"], sub["scale"])


def test_fields(sub):
    for k in ("vectors", "positions", "scale", "method", "contribution", "fit_pass_at_10"):
        assert k in sub, f"missing {k}"
    assert sub["positions"] in ("prefix", "read", "context")
    assert sub["method"].strip()


def test_contribution(sub):
    n = len((ROOT / sub["contribution"]).read_text().split())
    assert 40 <= n <= 300, f"contribution has {n} words"


def test_score_reproduces(sub, rerun):
    assert abs(rerun["pass_at_10"] - sub["fit_pass_at_10"]) <= 0.01, "re-run does not reproduce the reported score"

