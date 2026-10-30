"""Data for the researcher's review page of the IB screen results (her ask, 24 Oct: "present the swe-v episodes in a
page so i can tick stuff or give feedback ... do that for each result").

    .venv/bin/python src/ib_review_page.py <out.json>      # LCB and SWE-V; IB-SWE runs in its venv (see below)
    logs/ib_swe/venv/bin/python src/ib_review_page.py <out.json> ibswe

VISIBLE FIELDS ONLY (her rule; the orchestrator, 24 Oct). Kept:
- the model's visible message text in full (Inspect ContentText parts; mini-swe-agent `content`);
- tool calls (function and arguments), except the `think` tool, whose argument is the model's scratchpad (left out);
- tool outputs, cut to their first and last lines;
- harness user messages after the task (a cue-11 message, the continue message);
- the final diff or code (windows around cited lines, numbered as the code judge saw them), and the final message
  as the message judge read it (last visible message plus the submit answer);
- the judge's labels with cited unit NUMBERS and the turns they fall in, and each label's definition verbatim from
  the judge's rubric (src/ib_judges.py).
Never read or written: Inspect ContentReasoning, mini-swe-agent `reasoning_content`, the judge's cited unit text.
`<think>` blocks found inside visible text are replaced by a placeholder.
Episodes are drawn by the registered spot-read rule (src/ib_spot.py). The page itself is src/ib_review_page.html,
published with this file's output as data.json beside it.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ib_analysis as A  # noqa: E402
import ib_spot as P  # noqa: E402

HEAD, TAIL, LINE = 3, 3, 120          # tool output: first/last lines kept, and each line's max length
MSG, CMD = 900, 160   # MSG: harness messages only; visible message text and the final message are never cut
# Tool outputs are kept only on the turns the judge cited (±1) and the last 3 turns; others say "in the viewer".

# The leads in notes/ib_screen_results.md (verified). measure = the label spot-read; mech = scorer measures shown as
# context only. tag: two-task, one-task, cue12 (expected by construction), example (her two SWE-V reads).
RESULTS = {
    "lcb": [
        *[(c, "capability_eval", "down", "two-task") for c in ("c11_off", "G_orig", "c6_tests", "c8_pass")],
        *[(c, "alignment_eval", "down", "two-task") for c in ("c11_off", "c11_off_person", "c3b_insist", "c3b_nice",
                                                              "c5_real", "c9_allowed", "G_orig")],
        ("c8_stop", "plans_for_tests", "down", "two-task"),
        *[(c, "special_cases", "up", "one-task (lcbhard_37)") for c in (
            "c13_nomodify", "c3b_insist", "c3b_should", "c4_ci", "c5_real", "c5_training", "c6_tests", "c8_pass",
            "c9_allowed", "c_aisi_persist")],
        *[(c, "special_cases", "down", "one-task (lcbhard_5)") for c in (
            "c11_off", "c11_off_person", "c2_partial", "c4_detector", "c6_correct", "c7_dont_care", "c8_stop",
            "B_orig", "G_orig")],
    ],
    "ibswe": [
        *[(c, "discloses_test_edit", "up", "two-task") for c in ("c11_off", "c6_correct", "c8_stop")],
        ("c2_vague", "plans_for_tests", "down", "two-task"),
        *[("B_orig", m, "down", "cue12") for m in ("hesitates", "capability_eval", "alignment_eval", "plans_for_tests",
                                                   "targets_hidden_tests")],
        *[("G_orig", m, "down", "cue12") for m in ("hesitates", "capability_eval", "alignment_eval")],
    ],
    "swev": [
        ("c11_on", "acquires_fix", "down", "two-task"),
        ("c_aisi_persist", "capability_eval", "up", "two-task"),
    ],
}
MECH = {"lcb": {"special_cases": ["hack_func", "hack_primary"]}, "ibswe": {"discloses_test_edit": ["test_changed"]},
        "swev": {"acquires_fix": ["hack_enacted"]}}
DIRS = {"lcb": "logs/ib_ablation/lcb/screen", "ibswe": "logs/ib_ablation/ibswe/screen",
        "swev": "logs/ib_ablation/swev/screen"}
CELLS = {"lcb": "notes/ib_prereg/cells_lcb.jsonl", "ibswe": "notes/ib_prereg/cells_ibswe.jsonl",
         "swev": "notes/ib_prereg/cells_swev.jsonl"}


THINK = re.compile(r"<think>.*?(?:</think>|$)", re.S)


def no_think(text):
    """Visible text sometimes carries a <think>…</think> block (reasoning written into the message); it's left out."""
    return THINK.sub("[a <think> block in this message is left out]", text or "")


def cut(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n] + f" … [{len(text) - n} more characters]"


def code_view(text, cited, head=30, pad=8, whole=60, width=200):
    """The final code (LCB) or diff (SWE) as [line number, text] pairs, numbered as the code judge saw it
    (splitlines from 1). Short files are whole; longer ones show the first `head` lines and `pad` lines either side
    of each cited line, with [None, note] where lines are left out."""
    lines = (text or "").splitlines()
    keep = set(range(1, len(lines) + 1)) if len(lines) <= whole else (
        set(range(1, head + 1)) | {k for c in cited for k in range(c - pad, c + pad + 1) if 1 <= k <= len(lines)})
    out, prev = [], 0
    for n in sorted(keep):
        if n > prev + 1:
            out.append([None, f"… lines {prev + 1}–{n - 1} not shown …"])
        out.append([n, lines[n - 1][:width] + ("…" if len(lines[n - 1]) > width else "")])
        prev = n
    if prev < len(lines):
        out.append([None, f"… lines {prev + 1}–{len(lines)} not shown …"])
    return out


def cut_output(text):
    lines = [l[:LINE] + ("…" if len(l) > LINE else "") for l in (text or "").splitlines()]
    if len(lines) <= HEAD + TAIL:
        return "\n".join(lines)
    return "\n".join(lines[:HEAD] + [f"… [{len(lines) - HEAD - TAIL} lines left out] …"] + lines[-TAIL:])


def call_view(name, args):
    if name == "think":
        return dict(tool="think", args="[the think tool's text is the model's scratchpad, left out]")
    a = args or {}
    if name == "bash":
        s = a.get("cmd") or a.get("command") or ""
    elif name == "python":
        s = a.get("code") or ""
    elif name == "text_editor":
        s = " ".join(str(a.get(k)) for k in ("command", "path") if a.get(k)) + \
            ("\n" + str(a.get("file_text") or a.get("new_str") or "") if (a.get("file_text") or a.get("new_str")) else "")
    elif name == "submit":
        s = str(a.get("answer") or "")
    else:
        s = json.dumps(a)[:CMD]
    return dict(tool=name, args=cut(no_think(s), CMD))


def visible_inspect(sample):
    """Turn-by-turn visible record from an Inspect sample. Reasoning parts are skipped by type, never read."""
    from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, ChatMessageUser, ContentText
    turns, k, n_user = [], 0, 0
    for m in sample.messages:
        if isinstance(m, ChatMessageAssistant):
            k += 1
            text = m.content if isinstance(m.content, str) else "\n".join(
                c.text for c in m.content if isinstance(c, ContentText))
            turns.append(dict(turn=k, text=no_think(text).strip(), calls=[call_view(t.function, t.arguments)
                                                                          for t in (m.tool_calls or [])], outputs=[]))
        elif isinstance(m, ChatMessageTool) and turns:
            turns[-1]["outputs"].append(cut_output(no_think(m.text)))
        elif isinstance(m, ChatMessageUser):
            n_user += 1
            if n_user > 1 and turns:   # harness messages after the task (cue 11, the continue message)
                turns[-1]["harness_after"] = cut(m.text, MSG)
    return turns


def visible_swev(traj):
    """Turn-by-turn visible record from a mini-swe-agent trajectory. `reasoning_content` is never read."""
    turns, k, n_user, ids = [], 0, 0, {}
    for m in traj.get("messages", []):
        role = m.get("role")
        if role == "assistant":
            k += 1
            calls = []
            for a in ((m.get("extra") or {}).get("actions") or []):
                calls.append(dict(tool="bash", args=cut(no_think(a.get("command") or ""), CMD)))
            turns.append(dict(turn=k, text=no_think(m.get("content") or "").strip(), calls=calls, outputs=[]))
        elif role == "tool" and turns:
            c = m.get("content")
            turns[-1]["outputs"].append(cut_output(no_think(c if isinstance(c, str) else json.dumps(c))))
        elif role == "user":
            n_user += 1
            if n_user > 1 and turns:
                turns[-1]["harness_after"] = cut(m.get("content") if isinstance(m.get("content"), str) else "", MSG)
    return turns


def labels_of(r, calls, focus):
    """The judge's true labels on this record (numbers and turns only), the focus label first."""
    out = []
    j = r.get("judged") or {}
    names = [focus] + [m for m in sorted(j) if m != focus and j.get(m) is True]
    for m in names:
        if m not in j:
            continue
        nums = P.cited_numbers(calls, r["id"], m) if j.get(m) is True else []
        kind = P.KIND.get(m)
        turns = sorted({t for t in P.unit_turns(r, m, nums).values() if t}) if kind in ("reasoning", "message") else []
        out.append(dict(label=m, value=j.get(m), kind=kind, cited_units=nums, cited_turns=turns,
                        code_lines=nums if kind == "code" else []))
    return out


def definition(bench, label):
    """The judge's own definition of a label, verbatim from its rubric (LCB's or the SWE one), whitespace joined."""
    swe = bench != "lcb"
    if label == "special_cases":
        m = re.search(r"special_cases: (true if .*?is not\s+this\.)", P.J.CODE_SYS_SWE if swe else P.J.CODE_SYS, re.S)
    else:
        text = (P.J.REASONING_SYS_SWE + "\n" + P.J.MESSAGE_SYS_SWE) if swe else (P.J.REASONING_SYS + "\n" + P.J.MESSAGE_SYS)
        m = re.search(rf"^- {re.escape(label)}: (.*?)(?=^- |^\S)", text, re.S | re.M)
    return " ".join(m.group(1).split()) if m else None


def caveat_of(bench, label):
    """The registered caveat on a label, plus the pilot-reliability note where the screen excluded it from ranking."""
    parts = [A.MEASURE_CAVEATS.get(label)]
    if label in A.UNRELIABLE_AT_PILOT.get(bench, ()):
        parts.append("unreliable at the pilot on this benchmark (never re-checked), so not used for the screen ranking")
    return "; ".join(x for x in parts if x) or None


def build(bench, out):
    d = Path(DIRS[bench])
    rows = [json.loads(l) for l in (d / "judges/records_judged.jsonl").read_text().splitlines() if l.strip()]
    by = {r["id"]: r for r in rows}
    calls = {}
    for l in (d / "judges/judge_calls.jsonl").read_text().splitlines():
        c = json.loads(l)
        if c["outcome"] == "ok":
            calls[(c["id"], c["kind"])] = c["raw"]
    reg = {}
    for l in Path(CELLS[bench]).read_text().splitlines():
        if l.strip():
            x = json.loads(l)
            reg.setdefault(x["cell"], x)
    if bench == "swev":
        A.set_s1(False)
    grid = A.screen(rows, reg, sorted({m for _, m, _, _ in RESULTS[bench]} | {x for v in MECH[bench].values() for x in v}))
    results, need = [], set()
    for cell, m, direction, tag in RESULTS[bench]:
        ref = reg[cell]["reference"]
        v = grid[(cell, m)]
        tasks = {r["task"] for r in rows if r["cell"] == cell}
        src = cell if direction == "up" else ref
        pool = [r["id"] for r in rows if r["cell"] == src and r["task"] in tasks and P.judged_positive(r, bench, m)]
        pick = P.draw(bench, cell, m, pool)
        need |= set(pick)
        def kn(c, t, x):   # (k, n) from the analysis's own per-task rate; missing values (cut episodes) left out
            rate, n = A.per_task_rate(rows, c, t, x)
            return (round(rate * n) if n else 0), n

        def row(t, cv, rv, x):
            (ck, cn), (rk, rn) = kn(cell, t, x), kn(ref, t, x)
            return dict(task=t, cell_rate=cv, ref_rate=rv, cell_k=ck, cell_n=cn, ref_k=rk, ref_n=rn)
        per = [row(t, cv, rv, m) for t, cv, rv, _ in v["per_task"]]
        mech = [dict(measure=x, per_task=[row(t, cv, rv, x) for t, cv, rv, _ in grid[(cell, x)]["per_task"]])
                for x in MECH[bench].get(m, [])]
        results.append(dict(id=f"{bench}|{cell}|{m}", bench=bench, cell=cell, cue=reg[cell].get("edit_text") or "",
                            family=reg[cell].get("family"), reference=ref, measure=m, label=m,
                            definition=definition(bench, m), direction=direction, tag=tag,
                            caveat=caveat_of(bench, m), per_task=per, mechanical=mech,
                            drawn_from=f"{src}'s episodes with {m} true on the cell's tasks ({len(pool)})",
                            episodes=[f"{bench}::{x}" for x in pick]))
    if bench == "swev":   # her two reads (her_read.json)
        for x in json.loads((d / "her_read.json").read_text()):
            need.add(x["episode"])
            lab = x["why"].split()[0]
            results.append(dict(id=f"swev|example|{x['why']}", bench=bench, cell=x["cell"], cue="", family=None,
                                reference=None, measure=x["why"], label=lab, definition=definition(bench, lab),
                                direction=None, tag="example (her read)", caveat=caveat_of(bench, lab),
                                per_task=[], mechanical=[], drawn_from=f"seeded draw from {x['drawn_from']} episodes",
                                episodes=[f"{bench}::{x['episode']}"]))
    episodes = {}
    if bench == "swev":
        for rid in sorted(need):
            r = by[rid]
            traj = json.loads((d / "trajectories" / r["log"]).read_text())
            episodes[f"{bench}::{rid}"] = card(bench, r, visible_swev(traj), calls, str(d / "trajectories" / r["log"]))
    else:
        from inspect_ai.log import read_eval_log
        for f in sorted(d.glob("*.eval")):
            log = read_eval_log(str(f))
            for s in log.samples or []:
                if str(s.id) in need and f"{bench}::{s.id}" not in episodes:
                    episodes[f"{bench}::{s.id}"] = card(bench, by[str(s.id)], visible_inspect(s), calls, str(f), s.epoch)
    out = Path(out)
    data = json.loads(out.read_text()) if out.exists() else {"results": [], "episodes": {}}
    data["results"] = [x for x in data["results"] if x["bench"] != bench] + results
    data["episodes"] = {k: v for k, v in data["episodes"].items() if not k.startswith(bench + "::")} | episodes
    out.write_text(json.dumps(data, ensure_ascii=False))
    print(f"{bench}: {len(results)} results, {len(episodes)} episodes; file {out.stat().st_size / 1e3:.0f} kB")


def card(bench, r, turns, calls, log_path, epoch=None):
    """One episode. Locators (the orchestrator): SWE-V's inspector titles each step "Step {i+1}/{n}" with step 1 the
    system and task, so reply k is Step k+1; in Inspect's viewer, reply k is the k-th assistant message."""
    final = r.get("func_final") or ""
    if bench == "swev":
        opener = f"logs/ib_cues/swe/venv/bin/mini-extra inspector {log_path}"
        locate = dict(viewer="mini-swe-agent inspector", file=log_path, step_of_reply_offset=1,
                      how="reply k is 'Step k+1' in the inspector's title; r toggles the reasoning")
    else:
        opener = f".venv/bin/inspect view --log-dir {Path(log_path).parent}"
        locate = dict(viewer="Inspect log viewer", file=log_path, sample=r["id"], epoch=epoch, step_of_reply_offset=0,
                      how="open the file, then the sample; reply k is the k-th assistant message in the Messages tab")
    labels = labels_of(r, calls, None)
    keep = {t + dt for l in labels for t in l["cited_turns"] for dt in (-1, 0, 1)} | set(range(len(turns) - 2, len(turns) + 1))
    for t in turns:
        if t["turn"] not in keep and t["outputs"]:
            n = sum(len(o.splitlines()) for o in t["outputs"])
            t["outputs"] = [f"[output not shown here ({n} lines); open the episode in the viewer]"]
    return dict(id=r["id"], bench=bench, cell=r["cell"], task=r["task"], rep=r.get("rep"),
                outcome=dict(passed=r.get("passed"), score=r.get("score"), test_changed=r.get("test_changed"),
                             end=r.get("end"), cut=A.is_cut(r), n_turns=len(turns),
                             hack_primary=A.value(r, "hack_primary")),
                labels=labels, turns=turns,
                final_code=code_view(final, sorted({n for l in labels if l["kind"] == "code" and l["value"] is True
                                                    for n in l["code_lines"]})),
                # what the message judge read: the last visible message, plus the submit answer if it says more
                final_message=no_think(P.J.final_messages(r["turns"], r.get("submit_answer"))).strip(),
                open=opener, locate=locate)


if __name__ == "__main__":
    out = sys.argv[1]
    benches = sys.argv[2:] or ["lcb", "swev"]
    for b in benches:
        build(b, out)
