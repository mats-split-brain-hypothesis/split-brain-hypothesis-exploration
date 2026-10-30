"""Free check (mockllm) for the file probe (notes/ib_persistence.md §15): with extra_file set, the file is in
/workspace beside func.py and test.py, byte for byte, and the prompt (system message and first user message) is the
same as the plain base's. Base = instruction=pass, framing=none, basic_agent loop (switch=none), lcbhard_27.

    python src/file_probe_mock.py <log dir>
"""
import hashlib
import sys

sys.path.insert(0, "src")
from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402

import ib_variants  # noqa: E402

CMD = "ls -A; for f in dummy.md CLAUDE.md; do [ -f \"$f\" ] && sha256sum \"$f\"; done; echo END"
CASES = {"base": ""} | {k: k for k in ib_variants.EXTRA_FILES}
seen = {}
for case, extra in CASES.items():
    model = get_model("mockllm/model", custom_outputs=[
        ModelOutput.for_tool_call(model="mockllm/model", tool_name="bash", tool_arguments={"cmd": CMD}),
        ModelOutput.for_tool_call(model="mockllm/model", tool_name="submit", tool_arguments={"answer": "DONE"})] * 3)
    task = ib_variants.ib_variant(instruction="pass", framing="none", label=f"fpmock_{case}", effort=None,
                                  extra_file=extra)
    s = inspect_eval(task, model=model, sample_id="lcbhard_27", log_dir=sys.argv[1], max_sandboxes=1,
                     display="none")[0].samples[0]
    sysm = next(m.text for m in s.messages if m.role == "system")
    user = next(m.text for m in s.messages if m.role == "user")
    out = next(m.text for m in s.messages if m.role == "tool")
    seen[case] = (sysm, user)
    want = ""
    if extra:
        name, text = ib_variants.EXTRA_FILES[extra]
        want = f"{hashlib.sha256(text.encode()).hexdigest()}  {name}"
    print(f"{case:16} files: {sorted(l for l in out.split() if '.' in l and len(l) < 20)} | file sha256 matches: "
          f"{(want in out) if extra else 'n/a'} | system same as base: {sysm == seen['base'][0]} | first user same as "
          f"base: {user == seen['base'][1]} | file named in prompt: "
          f"{bool(extra) and ib_variants.EXTRA_FILES[extra][0] in (sysm + user)}")
