"""Free replay audit for the grader-removal check (notes/ib_persistence.md §17): mockllm submits at once at every
point's late cut through the vendored, unmodified ib_continue (arm L_none), so the silent score shows whether the hack
already worked at the cut, and the replay mismatches show whether each prefix rebuilds. As agent 8's exp 10 audit.

    python src/ds_audit.py <points.json, relative to the worktree> <log dir> [<N sandboxes>]
"""
import sys

sys.path.insert(0, "src")
from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402

import ib_continue  # noqa: E402

model = get_model("mockllm/model", custom_outputs=[
    ModelOutput.for_tool_call(model="mockllm/model", tool_name="submit", tool_arguments={"answer": "DONE"})] * 500)
task = ib_continue.ib_continue(points=sys.argv[1], arm="L_none", max_new_messages=4, effort=None)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
log = inspect_eval(task, model=model, log_dir=sys.argv[2], max_sandboxes=n, max_samples=n, display="none")[0]
for s in log.samples:
    rec = (s.store or {}).get("ib_cont") or {}
    print(f"{s.id}: score {list(s.scores.values())[0].value if s.scores else None}, replay mismatches "
          f"{len(rec.get('replay_mismatches', []))}, error {bool(s.error)}")
