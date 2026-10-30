"""Launch agent 8's run_capped.py (unmodified) with one change: the spend guard's price for DeepSeek V4 Pro.

Agent 8's costs.py prices deepseek/deepseek-v4-pro at (1.30, 2.60, 1.30) $/M (input, output, cache read), so cached input
is charged at the full input price. Dark Mode trajectories are ~95% cached input, which makes the guard read ~4-6x the
real spend. This sets SiliconFlow's FP8 prices from agent 4's costs.py (OpenRouter endpoints listing, 2026-10-25):
(1.5016, 3.135, 0.135). run_spend's x1.3 bill markup still applies on top.

    PYTHONPATH=src python src/darkmode_ds_run.py <run_capped.py arguments>
"""
import runpy
import sys
from pathlib import Path

A8_SRC = Path(__file__).resolve().parents[1] / ".claude/worktrees/agent-8-user-facing/src"
sys.path.insert(0, str(A8_SRC))
import costs  # noqa: E402  (agent 8's module; run_spend does `from costs import PRICES`, the same dict object)

DEEPSEEK = "deepseek/deepseek-v4-pro"
costs.PRICES[DEEPSEEK] = (1.5016, 3.135, 0.135)

if __name__ == "__main__":
    import run_spend  # noqa: E402
    assert run_spend.PRICES[DEEPSEEK] == (1.5016, 3.135, 0.135), run_spend.PRICES[DEEPSEEK]
    sys.argv = [str(A8_SRC / "run_capped.py")] + sys.argv[1:]
    runpy.run_path(str(A8_SRC / "run_capped.py"), run_name="__main__")
