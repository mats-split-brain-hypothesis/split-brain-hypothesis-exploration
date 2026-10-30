"""Run launch 2 of the 1g scale-up: the interleaved task (src/scale1g_task.py), at most --max-sandboxes episodes at once,
with run_variants' own-spend cap and the shared key's global stop ($10).

  .venv/bin/python src/run_scale1g.py --log-dir logs/ib_cues/scale1g_launch2 --cap 26 [--cells all|pass]

--cells pass keeps only the two "pass all the tests" cells (option A; the pre-registered fallback when the key has
under $60 left at launch).
"""
import argparse
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai import eval
from inspect_ai.model import get_model

sys.path.insert(0, str(Path(__file__).parent))
from run_spend import own_spend  # noqa: E402
from run_variants import ENV, log_line, remaining, watchdog  # noqa: E402
from scale1g_task import scale1g_interleaved  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", required=True)
    p.add_argument("--cap", type=float, required=True)
    p.add_argument("--max-sandboxes", type=int, default=3)
    p.add_argument("--cells", choices=["all", "pass"], default="all")
    a = p.parse_args()
    load_dotenv(ENV)
    Path(a.log_dir).mkdir(parents=True, exist_ok=True)
    log = Path(a.log_dir) / "watchdog.log"
    spent_before = own_spend(a.log_dir)[1]
    rem = remaining()
    log_line(log, f"start, own spend so far ~${spent_before:.2f}, key remaining ${rem:.2f}, cap ${a.cap}, cells {a.cells}")
    if rem < 10:
        raise SystemExit("key below $10: global stop")
    threading.Thread(target=watchdog, args=(a.log_dir, a.cap, log, spent_before), daemon=True).start()
    t = scale1g_interleaved()
    ids = [s.id for s in t.dataset if a.cells == "all" or s.metadata["cell"].startswith("S_pass")]
    model = get_model("openrouter/qwen/qwen3.8-2.4t-a95b", provider={"order": ["siliconflow/fp8"], "allow_fallbacks": False})
    eval(t, model=model, sample_id=ids, max_samples=a.max_sandboxes, max_sandboxes=a.max_sandboxes,
         max_connections=a.max_sandboxes, fail_on_error=False, log_dir=a.log_dir, display="plain")
