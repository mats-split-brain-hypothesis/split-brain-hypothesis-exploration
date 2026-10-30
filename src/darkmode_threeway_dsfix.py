"""Dark Mode three-way for DeepSeek V4 Pro, with one harness fix: resample broken no-tool-call replies.

On SiliconFlow, DeepSeek sometimes returns a reply with no parsed tool call whose text holds only the leftovers of one
("</parameter>", "</invoke>") or is empty. Agent 8's loop (aie_puppeteer, imported read-only) treats any reply without a
tool call as the final reply and ends the episode, so 21 of 30 DeepSeek episodes ended before the screenshot step.

Fix: when a generated reply has no tool call AND its text is empty or contains tool-call residue, discard it and generate
again on the same messages, up to 3 times (no message is added). A reply with no tool call and no residue (a real final
reply or plain narration) ends the episode as before. Each discarded reply is counted in the sample store under
"ds_resamples" ([{"residue": bool, "chars": n}]).

    PYTHONPATH=src python src/darkmode_ds_run.py --task darkmode_threeway_dsfix ...
"""
import re

import darkmode_threeway  # noqa: F401  (registers framing "ci" and its first message on agent 8's module)
from darkmode_threeway import ap

RESIDUE = re.compile(r"</?parameter|</?invoke|<tool_call|function_calls")
MAX_RESAMPLES = 3
_get_model = ap.get_model


def broken(msg) -> bool:
    """A reply that would end the episode but holds no real final answer: no tool call, and empty or residue."""
    if msg.tool_calls:
        return False
    text = msg.text or ""
    return (not text.strip()) or bool(RESIDUE.search(text))


class _Resampling:
    def __init__(self, model):
        self._m = model

    def __getattr__(self, name):
        return getattr(self._m, name)

    async def generate(self, *args, **kwargs):
        from inspect_ai.util import store
        out = await self._m.generate(*args, **kwargs)
        for _ in range(MAX_RESAMPLES):
            if not broken(out.message):
                break
            text = out.message.text or ""
            log = store().get("ds_resamples", [])
            log.append({"residue": bool(RESIDUE.search(text)), "chars": len(text)})
            store().set("ds_resamples", log)
            out = await self._m.generate(*args, **kwargs)
        return out


def _patched_get_model(*args, **kwargs):
    return _Resampling(_get_model(*args, **kwargs))


ap.get_model = _patched_get_model  # aie_puppeteer's solve looks up get_model in its module globals at call time


def darkmode_threeway_dsfix(effort=None, label=None, **kw):
    """run_capped's factory: agent 8's task, this project's first message, the resampling fix."""
    return ap.aie_puppeteer(effort=effort, label=label, **kw)
