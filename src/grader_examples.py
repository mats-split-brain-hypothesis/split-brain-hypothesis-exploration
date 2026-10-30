"""Examples for the dashboard's grader-beliefs tab, picked by rule (the first episode, in file order, that fits).

  python src/grader_examples.py <logs/data> <pre-commit runs dir>    # writes logs/grader/dashboard/a5_examples.json

Each example: the grader cue (highlighted), what the model did next (commands, short), a short reasoning excerpt
(Goodfire's judge quote for the first hack flag, or one sentence for School of Reward Hacks), and the outcome.
Excerpts are cut short on purpose.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import grader_actions as GA  # noqa: E402
import precommit_grader as PG  # noqa: E402

CUT = lambda s, n: s if len(s) <= n else s[:n].rstrip() + "…"  # noqa: E731
CHECK = {"inspect_content", "inspect_mechanics", "change_check"}


def ib_episode(gdir, key, row):
    with open(Path(gdir) / "goodfire" / f"{key}_traces.jsonl") as f:
        for i, line in enumerate(f):
            if i == row:
                return json.loads(line)["traces"][0]


def judge(gdir, path, row):
    with open(Path(gdir) / path) as f:
        for i, line in enumerate(f):
            if i == row:
                return json.loads(line)


def calls_after(t, node, kind, n=3):
    out = []
    for k, nd in enumerate(t["nodes"]):
        m = nd["message"]
        if k <= node or m["role"] != "assistant" or not nd.get("sampled", True):
            continue
        for tc in m.get("tool_calls") or []:
            a = GA.args_of(tc)
            p = GA.purpose_ib(tc.get("name"), a) if kind == "IB" else GA.purpose_swe(a)
            if p is None:
                continue
            c = str(a.get("cmd") or a.get("command") or a.get("code") or a.get("path") or "")
            c = re.sub(r"\s+", " ", c.replace("cd /workspace && ", ""))
            label = tc.get("name") if tc.get("name") != "bash" else "bash"
            if tc.get("name") == "text_editor":
                c = f"{a.get('command')} {a.get('path')}"
            out.append(f"[{p}] {label}: {CUT(c, 110)}")
            if len(out) == n:
                return out
    return out


def first_flag(j):
    fl = [f for f in j.get("flags") or [] if f.get("status") in ("enacted", "attempted") and f.get("node_index") is not None]
    return min(fl, key=lambda f: f["node_index"]) if fl else None


def main(gdir, pc_dir):
    rows = json.loads((ROOT / "logs" / "grader" / "actions_rows.json").read_text())
    ex = []
    keys = {"Qwen": "qwen", "GLM": "glm-5.2-fp8", "Kimi": "kimi-k3"}

    # Finding 1: a rejection, then check-facing calls, then the first hack flag before the next rejection (Qwen).
    for r in rows:
        if r["bench"] != "ImpossibleBench impossible" or r["model"] != "Qwen" or r["verdict_enacted"] != "yes" or r["first_hack"] is None:
            continue
        fb = [f for f in r["fb"] if f < r["first_hack"]]
        if not fb:
            continue
        f = fb[-1]
        win = [p for n, p in r["acts"] if n > f][:3]
        if not any(p in CHECK for p in win):
            continue
        t = ib_episode(gdir, "qwen", r["row"])
        j = judge(gdir, "goodfire/qwen_judge_rollouts.jsonl", r["row"])
        fl = first_flag(j)
        cue = t["nodes"][f]["message"]["content"]
        ex.append({"title": f"ImpossibleBench · Qwen · {r['task']}: rejection, then the tests, then a hack",
                   "finding": "Finding 1", "source": "Goodfire transcript (impossible split)",
                   "picked": "first Qwen hack episode (verdict) whose first hack flag follows a rejection with check-facing calls",
                   "context": CUT(cue, 260), "cue_hl": FEEDBACK_HL,
                   "action": "\n".join(calls_after(t, f, "IB")),
                   "reasoning": f"Judge quote ({fl['category']}, {fl['status']}): {CUT(fl['quote'], 220)}",
                   "outcome": f"Judge: verdict {j['verdict']}, enacted {j['verdict_enacted']}; categories "
                              f"{', '.join(r['hack_cats'])}"})
        break
    # Finding 1, no-hack side: a rejection followed by hashing test.py (Qwen).
    for r in rows:
        if r["bench"] != "ImpossibleBench impossible" or r["model"] != "Qwen" or r["verdict_enacted"] != "no":
            continue
        hit = next((f for f in r["fb"] if "inspect_mechanics" in [p for n, p in r["acts"] if n > f][:3]), None)
        if hit is None:
            continue
        t = ib_episode(gdir, "qwen", r["row"])
        j = judge(gdir, "goodfire/qwen_judge_rollouts.jsonl", r["row"])
        ex.append({"title": f"ImpossibleBench · Qwen · {r['task']}: rejection, then it hashes the test file",
                   "finding": "Finding 1", "source": "Goodfire transcript (impossible split)",
                   "picked": "first Qwen no-hack episode (verdict) with a hash of test.py right after a rejection",
                   "context": CUT(t["nodes"][hit]["message"]["content"], 260), "cue_hl": FEEDBACK_HL,
                   "action": "\n".join(calls_after(t, hit, "IB")), "reasoning": "",
                   "outcome": f"No enacted or attempted hack flag (judge verdict '{j['verdict']}', enacted "
                              f"'{j['verdict_enacted']}'); {len(r['fb'])} rejections in the episode."})
        break

    # Finding 2: hack before any rejection (Qwen; first flag enacted), cue = the prompt's instruction.
    for r in rows:
        if r["bench"] != "ImpossibleBench impossible" or r["model"] != "Qwen" or r["verdict_enacted"] != "yes" or r["first_hack"] is None:
            continue
        if any(f < r["first_hack"] for f in r["fb"]):
            continue
        t = ib_episode(gdir, keys["Qwen"], r["row"])
        j = judge(gdir, "goodfire/qwen_judge_rollouts.jsonl", r["row"])
        fl = first_flag(j)
        if fl["status"] != "enacted":
            continue
        prompt = next(nd["message"]["content"] for nd in t["nodes"] if nd["message"]["role"] == "user")
        before = [f"[{p}]" for n, p in r["acts"] if n < r["first_hack"]]
        ex.append({"title": f"ImpossibleBench · Qwen · {r['task']}: hack before any rejection",
                   "finding": "Finding 2", "source": "Goodfire transcript (impossible split)",
                   "picked": "first Qwen hack episode (verdict) whose first flag is enacted and comes before any rejection",
                   "context": CUT(prompt, 420), "cue_hl": "critically evaluate the unit tests",
                   "action": "Calls before the hack flag, by purpose: " + " ".join(before),
                   "reasoning": f"Judge quote ({fl['category']}, {fl['status']}): {CUT(fl['quote'], 220)}",
                   "outcome": f"Judge: verdict {j['verdict']}, enacted {j['verdict_enacted']}; categories "
                              f"{', '.join(r['hack_cats'])}"})
        break

    # Finding 3: SWE-bench Verified, a seek_answer call before the first hack flag (Qwen).
    swe_path = "goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack"
    for r in rows:
        if r["bench"] != "SWE-bench Verified" or r["model"] != "Qwen" or r["verdict_enacted"] != "yes" or r["first_hack"] is None:
            continue
        seek = [n for n, p in r["acts"] if p == "seek_answer" and n < r["first_hack"]]
        if not seek:
            continue
        with open(Path(gdir) / f"{swe_path}.traces.jsonl") as f:
            for i, line in enumerate(f):
                if i == r["row"]:
                    t = json.loads(line)["traces"][0]
                    break
        j = judge(gdir, f"{swe_path}.judge_rollouts.jsonl", r["row"])
        fl = first_flag(j)
        prompt = next(nd["message"]["content"] for nd in t["nodes"] if nd["message"]["role"] == "user")
        s = prompt.find("- Hidden test targeting")
        seek_cmds = [c for c in calls_after(t, seek[0] - 1, "SWE", 6) if c.startswith("[seek_answer]")][:2]
        ex.append({"title": f"SWE-bench Verified · Qwen · {r['task']}: looks for the fix outside the repo",
                   "finding": "Finding 3", "source": "Goodfire transcript (prompt with a 'Reward hacking' section)",
                   "picked": "first Qwen hack episode (verdict) with a seek_answer call before its first hack flag",
                   "context": CUT(prompt[s:], 330), "cue_hl": "speculating about what held-out tests assert",
                   "action": "\n".join(seek_cmds),
                   "reasoning": f"Judge quote ({fl['category']}, {fl['status']}): {CUT(fl['quote'], 220)}",
                   "outcome": f"Judge: verdict {j['verdict']}, enacted {j['verdict_enacted']}; categories "
                              f"{', '.join(r['hack_cats'])}"})
        break

    # Finding 4: pre-commit, a non-blocking hook committed while the grader is said to read the hooks folder;
    # and --no-verify while the grader is said to read the command log.
    pc = json.loads((ROOT / "logs" / "grader" / "precommit_rows.json").read_text())
    for cond, ch, why in (("grader_diff_hooks", "hooks", "a staged-files-only hook"),
                          ("grader_diff_hooks_cmds", "log", "--no-verify")):
        r = next(x for x in pc if x["cond"] == cond and ch in x["channels"])
        msgs = json.loads((Path(pc_dir) / cond / f"{r['run']}.json").read_text())
        user = next(m["content"] for m in msgs if m["role"] == "user")
        st = PG.steps(msgs)
        hook = next((c for c, _ in reversed(st[: r["step"] + 1]) if PG.HOOK_WRITE.search(c)), "")
        commit_cmd, commit_out = st[r["step"]]
        note = user[user.find("Note:"):]
        # the last reasoning sentence before the shortcut: in the turn that wrote the hook (hooks) or committed (log)
        key_cmd = hook if ch == "hooks" else commit_cmd
        turn = next((m for m in msgs if m.get("role") == "assistant" and any(c == key_cmd for _, c in PG.tool_calls(m))), {})
        rs = [x for x in re.split(r"(?<=[.!?])\s+|\n+", turn.get("reasoning_content") or "") if x.strip()]
        before = CUT(rs[-1], 260) if rs else ""
        ex.append({"title": f"Pre-commit · Kimi K2 Thinking · {cond}: commits with {why}",
                   "finding": "Finding 4", "source": "Model Forensics transcript",
                   "picked": f"first run in this arm with a shortcut via {ch}",
                   "context": CUT(note, 300), "cue_hl": note.split(" If ")[0],
                   "action": ("Hook: " + CUT(re.sub(r"\s+", " ", hook), 260) + "\n" if ch == "hooks" else "")
                             + "Commit: " + CUT(commit_cmd, 120) + "\n→ " + CUT(re.sub(r"\s+", " ", commit_out), 200),
                   "reasoning": (f"Last reasoning sentence before the {'hook write' if ch == 'hooks' else 'commit'}: "
                                 f"{before}") if before else "",
                   "outcome": f"Committed with the hook not blocking ({r['hook_why'] or 'bypassed'}); channel: {ch}."})

    # Finding 5: the same SoRH task without and with the count note.
    raw = ROOT / "logs" / "sorh_grader" / "raw"
    import csv
    with open(ROOT / "logs" / "grader" / "sorh_pilot_scores.csv") as f:
        sc = {(r["cell"], r["task"]): r for r in csv.DictReader(f)}
    tid = "sorh_147"
    for cell in ("none", "auto_count"):
        rec = json.loads((raw / cell / tid / "0.json").read_text())
        s = sc[(cell, tid)]
        sent = ""
        if cell == "auto_count":
            sents = re.split(r"(?<=[.!?])\s+|\n+", rec["reasoning"])
            # prefer a sentence that plans around the score; else the first that mentions it
            sent = next((x for x in sents if re.search(r"\b(score|density|arousal)\b", x, re.I)
                         and re.search(r"\b(maximi[sz]e|more|many|pack|increase|boost|high(er)?)\b", x, re.I)),
                        next((x for x in sents if re.search(r"\b(score|density|arousal)\b", x, re.I)), ""))
        ex.append({"title": f"School of Reward Hacks · Qwen · {tid} (social media post) · {cell}",
                   "finding": "Finding 5", "source": "Our pilot run (logs/sorh_grader)",
                   "picked": "the task with the largest rise in hack index whose replies are both under 150 words",
                   "context": rec["prompt"], "cue_hl": "Note: the reply is scored automatically" if cell != "none" else "",
                   "action": CUT(rec["reply"], 600),
                   "reasoning": CUT(sent, 200),
                   "outcome": f"{s['words']} words; hack index per 100 words {float(s['hack_index']):+.2f}; "
                              f"reasoning tokens {int(float(s['reasoning_tokens']))}"})
    out = ROOT / "logs" / "grader" / "dashboard" / "a5_examples.json"
    out.write_text(json.dumps(ex, indent=1, ensure_ascii=False))
    for e in ex:
        print("-", e["title"])


FEEDBACK_HL = "Your implementation failed the tests."

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
