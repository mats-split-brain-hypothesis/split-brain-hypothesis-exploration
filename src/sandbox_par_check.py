"""Free check (mockllm, no API calls): is --max-sandboxes per task or process-wide in Inspect 0.3.140 as run_variants
calls eval()? Three ib_variant tasks (arms), 2 samples each, every model output a 'sleep 15' bash call; eval() with the
same limits run_variants passes (max_sandboxes = max_samples = max_connections = N, max_tasks = 3). A watcher thread
counts this check's containers (names containing 'mockpar') every 2 s and prints the peak.

    python sandbox_par.py <N> <log dir>
"""
import subprocess
import sys
import threading
import time

sys.path.insert(0, "src")
from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402

import ib_variants  # noqa: E402

N = int(sys.argv[1])
peak, stop = [0], [False]


def watch():
    while not stop[0]:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
        n = sum("mockpar" in line for line in out.splitlines())
        peak[0] = max(peak[0], n)
        time.sleep(2)


threading.Thread(target=watch, daemon=True).start()
model = get_model("mockllm/model", custom_outputs=[
    ModelOutput.for_tool_call(model="mockllm/model", tool_name="bash", tool_arguments={"cmd": "sleep 15"})] * 60)
tasks = [ib_variants.ib_variant(instruction="pass", framing="automated", label=f"mockpar_{a}", effort=None,
                                message_limit=5, switch="control") for a in ("a", "b", "c")]
t0 = time.time()
inspect_eval(tasks, model=model, sample_id=["lcbhard_99", "lcbhard_58"], max_tasks=len(tasks), max_sandboxes=N,
             max_samples=N, max_connections=N, fail_on_error=False, log_dir=sys.argv[2], display="none")
stop[0] = True
print(f"N={N}: peak containers of this check at once: {peak[0]} (3 tasks x 2 samples); {time.time() - t0:.0f}s")
