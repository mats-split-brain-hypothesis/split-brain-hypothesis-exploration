"""Can the logged H_framing_none episodes serve as the regular arm (notes/ib_persistence.md §15b)? For each distinct
logged episode (round1a/round1c; a cancelled log and its retry count once), compare with today's setup: the system
and first user messages against today's build for that task (ib_variant(instruction=pass, framing=none), offline),
the tool definitions (attachments resolved) and the rejection wording (results and names removed) against today's
F_claude episode, the model, provider, effort, attempts and message limit. Prompt text and settings only.

    python src/file_probe_base_check.py
"""
import glob
import json
import re
import sys

sys.path.insert(0, "src")
from inspect_ai.log import read_eval_log  # noqa: E402

import ib_variants  # noqa: E402

task = ib_variants.ib_variant(instruction="pass", framing="none", effort="xhigh")
today = {s.id: (ib_variants.template(s.metadata["instruction_prompt"], 10, "full"), s.input) for s in task.dataset}


def first_model(s):
    return next(e for e in s.events if e.event == "model")


def tools(s):
    att = s.attachments or {}
    fix = lambda t: att.get(t.split("attachment://", 1)[1], t) if t.startswith("attachment://") else t
    return [(t.name, fix(t.description), json.dumps(t.parameters.model_dump(), sort_keys=True))
            for t in first_model(s).tools]


def rejection(s):
    m = next((m.text for m in s.messages if m.role == "user" and m.text.startswith("Your implementation failed")), None)
    if m is None:
        return None
    m = re.sub(r"Here are the test results:.*?(Please analyze)", r"<results>\1", m, flags=re.S)
    return m.split("To reiterate, this is your task:")[0]


ref_log = next(read_eval_log(fp) for fp in glob.glob("logs/ib_persistence/file_probe/*.eval")
               if (read_eval_log(fp, header_only=True).eval.task_args or {}).get("label") == "F_claude")
ref = ref_log.samples[0]
seen = {}
for fp in sorted(glob.glob("logs/ib_cues/round1*/*.eval")):
    log = read_eval_log(fp)
    ta = log.eval.task_args or {}
    if ta.get("label") != "H_framing_none":
        continue
    for s in log.samples or []:
        if s.error or (s.id, s.uuid) in seen:
            continue
        seen[(s.id, s.uuid)] = True
        sysm = next(m.text for m in s.messages if m.role == "system")
        user = next(m.text for m in s.messages if m.role == "user")
        rej = rejection(s)
        eff = (first_model(s).config.extra_body or {}).get("reasoning")
        print(f"{s.id} ep{s.epoch} ({fp.split('/')[-2]}, {log.status}): score {list(s.scores.values())[0].value} | "
              f"system = today {sysm == today[s.id][0]} | first user = today {user == today[s.id][1]} | tools = today "
              f"{tools(s) == tools(ref)} | rejection wording = today {None if rej is None else rej == rejection(ref)} | "
              f"model {log.eval.model == ref_log.eval.model} provider {log.eval.model_args == ref_log.eval.model_args} "
              f"effort {eff} | attempts {ta.get('attempts')} limit {log.eval.config.message_limit}")
