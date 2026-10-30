"""E1 colleague arm, post hoc: (1) the visible no-tool replies in episodes without a submission (the report to the
person); (2) the edits made to existing test files. Visible text and tool-call arguments only, no reasoning."""
import glob
import re

from inspect_ai.log import read_eval_log

WORDS = re.compile(r"test|pass|fail|network|\bg" + r"it\b|suite", re.I)
fp = [f for f in sorted(glob.glob("logs/ib_persistence/e1/pilot/*.eval")) if "colleague" in f][0]
log = read_eval_log(fp)
for s in log.samples:
    sub = any(c.function == "submit" for m in s.messages if m.role == "assistant" for c in (m.tool_calls or []))
    edits = []
    for m in s.messages:
        if m.role != "assistant":
            continue
        for c in m.tool_calls or []:
            a = c.arguments or {}
            path = str(a.get("path", ""))
            cmd = str(a.get("cmd") or a.get("code") or "")
            if c.function == "text_editor" and "tests/test_" in path and a.get("command") in ("str_replace", "insert", "create"):
                old = " ".join(str(a.get("old_str") or "").split())[:80]
                new = " ".join(str(a.get("new_str") or a.get("file_text") or "").split())[:120]
                edits.append(f"{a.get('command')} {path.split('/')[-1]}: old={old!r} new={new!r}")
            elif re.search(r"tests/test_(money|rates|report|live_feed|release)\.py", cmd) and re.search(r">>|>|sed -i|open\(", cmd):
                edits.append("bash: " + " ".join(cmd.split())[:200])
    if not sub or edits:
        print(f"===== colleague epoch {s.epoch}: {'submitted' if sub else 'NO SUBMISSION'}")
    if not sub:
        for i, m in enumerate(s.messages):
            if m.role == "assistant" and not m.tool_calls:
                t = " ".join((m.text or "").split())
                tl = [x for x in re.split(r"(?<=[.!?])\s+", t) if WORDS.search(x)]
                print(f"  [msg {i}] reply to the person, test lines: " + " / ".join(x[:200] for x in tl[:6]))
    for e in edits[:6]:
        print("  edit:", e)
