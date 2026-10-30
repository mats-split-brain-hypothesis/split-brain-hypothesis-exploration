"""ImpossibleBench LiveCodeBench ablation screen: every cell in ONE Inspect task, interleaved, each sample sending the
exact texts registered in a cells file (src/ib_cells.py build-lcb). Design: notes/ib_design.md.

  .venv/bin/inspect eval src/ib_ablation.py -T cells_file=notes/ib_prereg/cells_lcb.jsonl \
      -T tasks=lcbhard_37,lcbhard_5 -T cells=B,G -T reps=1 -T ref_reps=3 \
      --model openrouter/qwen/qwen3.8-2.4t-a95b -M provider='{"order": ["siliconflow/fp8"], "allow_fallbacks": false}' \
      --max-samples 3 --log-dir logs/ib_ablation/<stage>

Per sample (id "<cell>|<task>|r<rep>"): the system message, first user message, submit tool description and split
come from the cell's row; the cue-11 message (if any) is sent as its own user message right after reply 1's tool
results. One submission: the first submit ends the episode; the files are then scored by ImpossibleBench's
swe_style_humaneval_scorer (test edits kept). A reply without a tool call gets basic_agent's continue message, as in
every earlier IB run. The sample's store records: ib_cell, ib_submitted, ib_switch_sent, ib_switch_turn,
ib_test_changed_at_submit, ib_func_at_submit, ib_end ("submit" | "message_limit" | "model_length").
"""
import json
import random
import sys
from pathlib import Path

from inspect_ai import task, task_with
from inspect_ai.dataset import MemoryDataset
from inspect_ai.model import ChatMessageSystem, ChatMessageTool, ChatMessageUser, GenerateConfig, get_model
from inspect_ai.solver import chain, solver, use_tools
from inspect_ai.tool import bash, python, text_editor, think, tool
from inspect_ai.util import sandbox, store

sys.path.insert(0, str(Path(__file__).parent))
from ib_variants import THINK_DESCRIPTION, ib_variant, task_files  # noqa: E402
from inspect_ai.solver._basic_agent import DEFAULT_CONTINUE_MESSAGE as CONTINUE_MESSAGE  # noqa: E402

REF_CELLS = ("B", "G")
ORDER_SEED = "20261023|ib_lcb|order"


def load_cells(path):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    return {r["cell"]: r for r in rows}


def sample_plan(cells, tasks, reps, ref_reps, seed=ORDER_SEED, per_cell=None):
    """[(cell, task, rep)] in start order: a seeded shuffle of every (cell, task, rep), so cells interleave in time and
    the references' extra reps spread over the whole run. per_cell overrides the repeats of named cells."""
    per_cell = per_cell or {}
    n = lambda c: per_cell.get(c, ref_reps if c in REF_CELLS else reps)
    plan = [(c, t, r) for c in cells for t in tasks for r in range(1, n(c) + 1)]
    random.Random(seed).shuffle(plan)
    return plan


@tool
def submit():
    async def execute(answer: str):
        """Submit an answer for evaluation.

        Args:
          answer (str): Submitted answer
        """
        return answer
    return execute


@solver
def ablation_solver():
    from inspect_ai.model._call_tools import execute_tools
    from inspect_ai.tool._tool_with import tool_with

    @solver
    def init():
        async def solve(state, generate):
            md = state.metadata
            func_text, test_text = task_files(md)
            await sandbox().write_file("func.py", func_text)
            await sandbox().write_file("test.py", test_text)
            state.messages.insert(0, ChatMessageSystem(content=md["system"]))
            st = store()
            st.set("ib_cell", md["cell"])
            st.set("ib_test_original", test_text)
            return state
        return solve

    @solver
    def add_submit():
        async def solve(state, generate):
            state.tools.append(tool_with(submit(), "submit", state.metadata["submit_desc"]))
            return state
        return solve

    @solver
    def loop():
        async def solve(state, generate):
            if state.message_limit is None:
                state.message_limit = 50
            st = store()
            switch = state.metadata.get("switch")
            turn, end = -1, "message_limit"
            st.set("ib_submitted", False)
            st.set("ib_switch_sent", False)
            try:
                while not state.completed:
                    state.output = await get_model().generate(input=state.messages, tools=state.tools, cache=False)
                    state.messages.append(state.output.message)
                    turn += 1
                    if state.output.stop_reason == "model_length":
                        end = "model_length"
                        break
                    if not state.output.message.tool_calls:
                        state.messages.append(ChatMessageUser(content=CONTINUE_MESSAGE))
                    else:
                        results, _ = await execute_tools([state.output.message], state.tools)
                        state.messages.extend(results)
                        answer = next((r.text for r in results if isinstance(r, ChatMessageTool) and r.function == "submit"), None)
                        if answer:
                            state.output.completion = answer
                            st.set("ib_submitted", True)
                            st.set("ib_test_changed_at_submit", await sandbox().read_file("test.py") != st.get("ib_test_original"))
                            st.set("ib_func_at_submit", await sandbox().read_file("func.py"))
                            end = "submit"
                            break  # one submission
                    if switch and turn == 0:
                        state.messages.append(ChatMessageUser(content=switch))
                        st.set("ib_switch_sent", True)
                        st.set("ib_switch_turn", turn)
            except Exception as e:  # Inspect's message/time limits raise out of generate(); record why, re-raise
                end = "message_limit" if "message" in type(e).__name__.lower() or "message" in str(e).lower() else type(e).__name__
                raise
            finally:
                st.set("ib_end", end)
                if end != "submit":  # never submitted: keep the final files for the code checks
                    try:
                        st.set("ib_test_changed_at_submit", await sandbox().read_file("test.py") != st.get("ib_test_original"))
                        st.set("ib_func_at_submit", await sandbox().read_file("func.py"))
                    except Exception:
                        pass
            return state
        return solve

    tools = [bash(timeout=60), python(timeout=60), text_editor(timeout=60), think(THINK_DESCRIPTION)]
    return chain([init(), use_tools(tools, append=True), add_submit(), loop()])


@task
def ib_ablation(cells_file: str = "notes/ib_prereg/cells_lcb.jsonl", tasks: str = "lcbhard_37,lcbhard_5",
                cells: str = "", reps: int = 1, ref_reps: int = 3, effort: str = "xhigh", seed: str = ORDER_SEED):
    reg = load_cells(cells_file)
    specs = [c.strip() for c in cells.split(",") if c.strip()]
    per_cell = {c.split(":")[0]: int(c.split(":")[1]) for c in specs if ":" in c}  # "G:3" = 3 repeats of G per task
    chosen = [c.split(":")[0] for c in specs] or list(reg)
    missing = [c for c in chosen if c not in reg]
    assert not missing, f"cells not in {cells_file}: {missing}"
    task_ids = [t.strip() for t in tasks.split(",") if t.strip()]
    by_split = {}
    for split in {reg[c]["split"] for c in chosen}:
        by_split[split] = {str(s.id): s for s in ib_variant(split=split, instruction="neither", attempts=1).dataset}
    samples = []
    for cell, t, rep in sample_plan(chosen, task_ids, reps, ref_reps, seed, per_cell):
        row = reg[cell]
        base = by_split[row["split"]][t]
        md = {k: base.metadata[k] for k in ("prompt", "test", "entry_point", "task_id", "impossible_type")}
        md.update(cell=cell, rep=rep, split=row["split"], system=row["system"], first=row["first"],
                  test_rule=row.get("test_rule"), bench="lcb",
                  switch=row.get("switch"), submit_desc=row["submit_desc"], cells_file=cells_file)
        samples.append(base.model_copy(update={"id": f"{cell}|{t}|r{rep}", "input": row["first"], "metadata": md}))
    base_task = ib_variant(split="conflicting", instruction="neither", attempts=1, label="ablation")
    return task_with(base_task, name="ib_ablation_lcb", dataset=MemoryDataset(samples, name="ib_ablation_lcb"),
                     solver=ablation_solver(), config=GenerateConfig(extra_body={"reasoning": {"effort": effort}}),
                     message_limit=50, time_limit=14400)
