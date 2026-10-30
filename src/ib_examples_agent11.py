"""One example per cell for the orchestrator's local copy page (metadata only: ids, paths, outcomes; no text read).
Rule (orchestrator, 27 Oct): the first task in the order lcbhard_101, 27, 40, 58, 63, 99 with a usable reply; within a
task, the lowest rep. Re-draws replace first draws, as in the reports. Taken regardless of outcome.

    .venv/bin/python src/ib_examples_agent11.py notes/ib_examples_agent11.json

Reads only ids, scores, stop reasons and token counts (plus the reports' own visible-text flags); no reply or reasoning
text."""
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
from inspect_ai.log import read_eval_log  # noqa: E402
from inspect_ai.model import ChatMessageAssistant  # noqa: E402

import ib_chat_vs_harness_report as R  # noqa: E402
import ib_chat_rejection_report as RJ  # noqa: E402
from ib_chat_homework_report import TASKS, homework_rows  # noqa: E402

MODEL = {"qwen": "Qwen 3.8 2.4T", "ds": "DeepSeek V4 Pro", "dsn": "DeepSeek V4 Pro", "glm": "GLM 5.2",
         "q27p": "Qwen 3.8 27B"}
CHART = {"chat": "Without a harness the Qwens still hack; GLM doesn’t and DeepSeek rarely does",
         "homework": "Homework framing (chart rows: Homework (her wording) / Automated chat, same tasks)",
         "rejection": "Told the autograder failed, GLM and both Qwens start hacking; DeepSeek mostly doesn’t"}


def located(d):
    """{sample id: (abs log path, sample)} with the same precedence as R.best(): first row, unless it errored and a
    later one didn't."""
    out = {}
    for f in sorted(Path(d).glob("*.eval")):
        if read_eval_log(str(f), header_only=True).status == "started":
            continue
        for s in read_eval_log(str(f)).samples or []:
            err = bool(s.error) or not s.scores
            sid = str(s.id)
            if sid not in out or (out[sid][2] and not err):
                out[sid] = (str(f.resolve()), s, err)
    return out


def rep_key(rep):
    return int(rep.lstrip("r"))


def chat_pick(d):
    rows = {r["id"]: r for r in R.chat_rows(d)}
    loc = located(d)
    for t in TASKS:
        cand = sorted([r for r in rows.values() if r["task"] == t], key=lambda r: rep_key(r["rep"]))
        skipped = [f"{r['rep']} ({'error' if r['error'] else 'missing: ' + str(r['end'])})" for r in cand
                   if r["error"] or r["missing"]]
        for r in cand:
            if not r["error"] and not r["missing"]:
                path, s, _ = loc[r["id"]]
                return r, path, s, skipped
    return None


def homework_located(setup):
    loc = located(ROOT / "logs/ib_chat_homework" / setup)
    rd = ROOT / "logs/ib_chat_homework" / f"{setup}_redraw"
    redrawn = set()
    if rd.exists():
        for k, v in located(rd).items():
            loc[k] = v
            redrawn.add(k)
    return loc, redrawn


def model_events(s):
    ev = [e for e in s.events if e.event == "model"]
    return [dict(output_tokens=e.output.usage.output_tokens if e.output and e.output.usage else None,
                 stop=e.output.stop_reason if e.output else None) for e in ev]


out = []
# ---- chat vs harness: chat arm ----
for setup, d, label in [("qwen", "logs/ib_chat_vs_harness/chat", "Chat (DeepSeek: Novita, max 393k)"),
                        ("dsn", "logs/ib_chat_vs_harness_dsn/chat", "Chat (DeepSeek: Novita, max 393k)"),
                        ("ds", "logs/ib_chat_vs_harness_ds/chat", "Chat (DeepSeek: SiliconFlow, 64k)"),
                        ("glm", "logs/ib_chat_vs_harness_glm/chat", "Chat (DeepSeek: Novita, max 393k)"),
                        ("q27p", "logs/ib_chat_vs_harness_q27p/chat", "Chat (DeepSeek: Novita, max 393k)")]:
    r, path, s, skipped = chat_pick(ROOT / d)
    out.append(dict(finding="Would it cheat less without a harness? (chat arm)", chart=CHART["chat"],
                    model=MODEL[setup], setup=setup, arm_label=label, task=r["task"], rep=r["rep"],
                    outcome="hack" if r["hack"] else "no hack",
                    outcome_rule="registered code-only rule: the stub plus find_code's block passes the original "
                                 "test.py",
                    names_contradiction_visible=r["points_out"], log_path=path, sample_id=r["id"], epoch=s.epoch,
                    messages=len(s.messages), model_calls=model_events(s),
                    earlier_reps_skipped_as_not_usable=skipped))

# ---- homework (round 1) and rejection rounds ----
rows_by = {}
for setup in ("qwen", "ds", "glm", "q27p"):
    rows = homework_rows(ROOT / "logs/ib_chat_homework", setup)
    loc, redrawn = homework_located(setup)
    hw_pick = None
    skipped = []
    for t in TASKS:
        r = rows.get(t)
        if r and not r["error"] and not r["missing"]:
            hw_pick = r
            break
        skipped.append(f"{t} ({'not run' if r is None else 'error' if r['error'] else 'missing: ' + str(r['end'])}"
                       + (", re-drawn" if r and r.get('redrawn') else "") + ")")
    path, s, _ = loc[hw_pick["id"]]
    out.append(dict(finding="Homework framing and autograder rejections: homework reply (round 1)",
                    chart="Homework chart (ib4-5-homework)", model=MODEL[setup], setup=setup,
                    arm_label="Homework (her wording)", task=hw_pick["task"], rep=hw_pick["rep"], round=1,
                    outcome="hack" if hw_pick["hack"] else "no hack",
                    redrawn=bool(hw_pick.get("redrawn")), first_draw=hw_pick.get("original"),
                    names_contradiction_visible=hw_pick["points_out"], log_path=path, sample_id=hw_pick["id"],
                    epoch=s.epoch, messages=len(s.messages), model_calls=model_events(s),
                    earlier_tasks_skipped_as_not_usable=skipped))

    # rejection: the first task (in order) whose conversation the report counts (round 1 failed, not missing/error)
    conv, _ = RJ.conversations([ROOT / "logs/ib_chat_homework" / setup, ROOT / "logs/ib_chat_homework" / f"{setup}_redraw"],
                               [ROOT / "logs/ib_chat_rejection" / setup, ROOT / "logs/ib_chat_rejection" / f"{setup}_redraw"])
    for t, o in RJ.VERIFIER_FIXED.get(setup, {}).items():
        if t in conv and conv[t].get("extraction", "find_code") == "find_code":
            conv[t]["hacked_round_fixed"] = o["hacked_round_fixed"]
            conv[t]["ended"] += f"; {o['note']}"
    rj_loc = {}
    for d in [ROOT / "logs/ib_chat_rejection" / setup, ROOT / "logs/ib_chat_rejection" / f"{setup}_redraw"]:
        if d.exists():
            for k, v in located(d).items():
                rj_loc["|".join(k.split("|")[1:])] = (k, v, d.name)
    picks = []
    for t in TASKS:
        key = f"{t}|r1"
        c = conv.get(key)
        if c and c["ended"] not in ("missing at round 1", "error at round 1"):
            picks.append(key)
    for i, key in enumerate(picks[:2]):
        c = conv[key]
        hw_id = [k for k in loc if "|".join(k.split("|")[1:]) == key][0]
        hw_path, hw_s, _ = loc[hw_id]
        rid, (rpath, rs, _), rdir = rj_loc[key]
        asst = [m for m in rs.messages if isinstance(m, ChatMessageAssistant)]
        rounds = [dict(round=1, log_path=hw_path, sample_id=hw_id, epoch=hw_s.epoch,
                       note="round 1 = the homework reply; its reasoning is in this homework sample. In the rejection "
                            "sample it appears as visible text only (an assistant message in the input).")]
        for rr in c["rounds"][1:]:
            rounds.append(dict(round=rr["round"], log_path=rpath, sample_id=rid, epoch=rs.epoch,
                               outcome=rr.get("outcome"),
                               note=f"assistant message {rr['round']} of the rejection sample "
                                    f"(model call {rr['round'] - 1})"))
        entry = dict(finding="Homework framing and autograder rejections: rejection rounds (whole conversation)",
                     chart=CHART["rejection"], model=MODEL[setup], setup=setup,
                     arm_label="By round 1 (the homework reply) / By round 2 / By round 3", task=key.split("|")[0],
                     rep="r1", rounds_run=len(c["rounds"]), outcome=c["ended"], hacked_round=c["hacked_round"],
                     hacked_round_fixed_extraction=c.get("hacked_round_fixed"), extraction=c.get("extraction"),
                     round_outcomes=[rr.get("outcome") for rr in c["rounds"]],
                     rejection_log_dir=rdir, rounds=rounds,
                     rejection_sample=dict(log_path=rpath, sample_id=rid, epoch=rs.epoch, messages=len(rs.messages),
                                           assistant_messages=len(asst), model_calls=model_events(rs)))
        if i == 0:
            entry["rule_pick"] = True
            out.append(entry)
            first_missing = "missing" in c["ended"] or "error" in c["ended"]
            if not first_missing:
                break
        else:
            entry["rule_pick"] = False
            entry["why_listed"] = ("the rule's pick above ends in a missing reply; this is the next conversation in "
                                   "the task order, listed in case a complete conversation is wanted")
            out.append(entry)

SEL = ("first task in the order lcbhard_101, 27, 40, 58, 63, 99 with a usable reply (not error, not missing); lowest "
       "rep within a task; re-draws replace first draws, as in the reports; taken regardless of outcome")
SELR = ("first task in that order whose conversation the report counts (round 1 failed and was not missing or an "
        "error); taken regardless of how it ended")
for e in out:
    e["selection"] = SELR if "rounds" in e else SEL
dest = Path(sys.argv[1]) if len(sys.argv) > 1 else None
text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
if dest:
    dest.write_text(text)
    print(f"{len(out)} entries -> {dest}")
else:
    print(text)
