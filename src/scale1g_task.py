"""1g scale-up, launch 2: all four cells in ONE Inspect task with an interleaved sample order, so episodes start
round-robin across cells (launch 1 ran one task per cell and the scheduler front-loaded the first cell).

The cells differ only in the instruction and the automated framing, which live in each sample's input and metadata
(instruction_prompt); the solver, scorer and sandbox are the same for every cell, so one task can carry all of them.
Each sample is a cell's own sample from ib_variant(...).dataset, re-identified as "<cell>|<task>|e<rep>" with
metadata cell / task_id / rep. Order: for rep in 1..reps, for each task (rotating the starting cell by task and rep),
the four cells in turn. With max_samples 3, Inspect starts samples in dataset order.

  .venv/bin/inspect eval src/scale1g_task.py ...   (normally via src/run_scale1g.py)
"""
import sys
from pathlib import Path

from inspect_ai import task, task_with
from inspect_ai.dataset import MemoryDataset

sys.path.insert(0, str(Path(__file__).parent))
from ib_variants import ib_variant  # noqa: E402

CELLS = [("S_pass_auto", "pass", "automated"), ("S_pass_none", "pass", "none"),
         ("S_neither_auto", "neither", "automated"), ("S_neither_none", "neither", "none")]
TASKS = "lcbhard_58,lcbhard_99,lcbhard_27,lcbhard_63,lcbhard_101"


def interleaved_order(tasks, reps):
    """[(cell, task, rep)] in start order: round-robin over cells, starting cell rotated per (task, rep)."""
    labels = [c for c, _, _ in CELLS]
    out = []
    for rep in range(1, reps + 1):
        for i, t in enumerate(tasks):
            rot = (i + rep - 1) % len(labels)
            for c in labels[rot:] + labels[:rot]:
                out.append((c, t, rep))
    return out


@task
def scale1g_interleaved(tasks: str = TASKS, reps: int = 2, effort: str = "xhigh"):
    task_ids = tasks.split(",")
    per_cell = {}
    for label, instruction, framing in CELLS:
        ds = ib_variant(instruction=instruction, framing=framing, effort=effort, label=label).dataset
        per_cell[label] = {str(s.id): s for s in ds}
    samples = []
    for cell, t, rep in interleaved_order(task_ids, reps):
        s = per_cell[cell][t]
        samples.append(s.model_copy(update={"id": f"{cell}|{t}|e{rep}",
                                            "metadata": {**(s.metadata or {}), "cell": cell, "task_id": t, "rep": rep}}))
    base = ib_variant(instruction="pass", framing="automated", effort=effort, label="scale1g")
    return task_with(base, name="ib_scale1g", dataset=MemoryDataset(samples, name="scale1g_interleaved"))
