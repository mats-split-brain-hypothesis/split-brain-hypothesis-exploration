"""Rebuild the completed samples of a stuck run from Inspect's sample buffer and write each task's log as
'cancelled' with those samples, so eval_retry re-runs only the rest.

  recover_buffer.py <run dir> <out dir> [--write]

Without --write, only checks the rebuild (message counts against the buffer's own summary). Messages = the last
model call's input + its output + the tool results after it (cut to the buffer's message count); store = the store events' patches applied in order.
"""
import os
import sys
from pathlib import Path

import jsonpatch
from pydantic import TypeAdapter

from inspect_ai.log import EvalSample, read_eval_log, write_eval_log
from inspect_ai.log._condense import resolve_sample_attachments
from inspect_ai.log._recorders.buffer.database import SampleBufferDatabase
from inspect_ai.log._transcript import Event
from inspect_ai.model import ChatMessageTool

EVENTS = TypeAdapter(list[Event])


def rebuild(db, summary):
    data = db.get_sample_data(id=summary.id, epoch=summary.epoch)
    events = [e for e in EVENTS.validate_python([e.event for e in data.events])
              if not getattr(e, "pending", None)]  # the buffer also keeps each call's in-progress copy
    s = EvalSample(id=summary.id, epoch=summary.epoch, input=summary.input, target=summary.target,
                   metadata=summary.metadata or {}, events=events,
                   attachments={a.hash: a.content for a in data.attachments}, messages=[])
    s = resolve_sample_attachments(s)
    models = [i for i, e in enumerate(s.events) if e.event == "model"]
    last = s.events[models[-1]]
    msgs = list(last.input) + [last.output.message]
    tools = {}  # each call logs a pending event (empty result) and a completed one with the same id: keep the last
    for e in s.events[models[-1] + 1:]:
        if e.event == "tool":
            tools[e.id] = e
    for e in tools.values():
        msgs.append(ChatMessageTool(content=e.result if isinstance(e.result, str) else str(e.result),
                                    tool_call_id=e.id, function=e.function, error=e.error))
    msgs = msgs[:summary.message_count]  # past a message limit the tool results never reached the state
    store = {}
    for e in s.events:
        if e.event == "store":
            store = jsonpatch.apply_patch(store, [c.model_dump(by_alias=True, exclude_none=True) for c in e.changes])
    limit = next((e for e in s.events if e.event == "sample_limit"), None)
    dump = lambda v: v.model_dump() if hasattr(v, "model_dump") else v
    d = s.model_dump()
    d.update(messages=[m.model_dump() for m in msgs], store=store,
             scores={k: dump(v) for k, v in (summary.scores or {}).items()},
             model_usage={k: dump(v) for k, v in (summary.model_usage or {}).items()},
             total_time=summary.total_time, working_time=summary.working_time, uuid=summary.uuid,
             limit=(None if limit is None else dict(type=limit.type, limit=limit.limit)), attachments={})
    return EvalSample.model_validate(d)


run, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for f in sorted(run.glob("*.eval")):
    db = SampleBufferDatabase(os.path.realpath(f), create=False)
    got = db.get_samples()
    done = [x for x in (got.samples if got else []) if x.completed]
    rebuilt = []
    for x in done:
        s = rebuild(db, x)
        print(f"{f.name[26:]} {x.id}: messages rebuilt {len(s.messages)} vs buffer count {x.message_count}; "
              f"score {[v.value for v in s.scores.values()]}; limit {s.limit}; store keys {sorted(s.store)}")
        rebuilt.append(s)
    if "--write" in sys.argv:
        log = read_eval_log(str(f), header_only=True)
        log = log.model_copy(update=dict(status="cancelled", samples=rebuilt))
        write_eval_log(log, str(out / f.name))
        print("   wrote", out / f.name, len(rebuilt), "samples")
