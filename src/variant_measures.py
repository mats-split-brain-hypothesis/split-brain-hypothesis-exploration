"""Step 3: does each ImpossibleBench harness change move persistence and not hesitation, or the reverse?

  python src/variant_measures.py <labels.jsonl[,labels2.jsonl]> --logs <dir> [<dir> ...] [--variants A,B] [--tasks t1,t2]
      [--alias <file-name or label substring>=<label>,...] [--json out.json]

<labels.jsonl>: src/cot_labels.py output for the episodes (Inspect loader; ids "<log stem>|<sample id>|<epoch>").
--logs: directories of Inspect .eval logs from src/run_variants.py (agent 2's logs/ib_cues/round1a and agent 4's
logs/ib_persistence/step3). Episodes are grouped by the variant label in each log's task_args.

Per variant (episodes pooled):
- hack: the episode passed (score C) on the conflicting split, where only a hack can pass;
- how it ended: passed / cut by the 50-message limit / text reply with the nudge off / submissions used up;
- persistence (labeller): new task-aimed candidates per 1,000 reasoning tokens, overall and after the first
  rejection; new check-aimed candidates the same way (check-persistence, kept apart);
- persistence (actions): submissions, and turns after the first rejection;
- hesitation (actions): the message index of the first submit (agent 2's note: L_attempts1 held it to 49/50);
- hesitation (labeller): correctness doubts and legitimacy doubts per 1,000 reasoning tokens;
- awareness: A, G, S sentences per 1,000 reasoning tokens.
Reasoning tokens: characters / 3.0 (the ratio measured on Goodfire's Qwen transcripts, src/persistence_measures.py).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

from inspect_ai.log import read_eval_log

FEEDBACK = "Your implementation failed the tests"
RECORDED = "Your submission has been recorded"
CPT = 3.0


def episodes(dirs, variants=None, tasks=None, alias=None):
    """alias: {substring of a log file name or of a variant label: label to use}, e.g. the effort pilot's stock xhigh
    log -> L_base, agent 7's L_recorded -> L_feedback_none."""
    alias = alias or {}
    for d in dirs:
        for fp in sorted(Path(d).glob("*.eval")):
            log = read_eval_log(str(fp))
            if log.status not in ("success", "cancelled", "error"):
                continue  # still running
            args = log.eval.task_args or {}
            label = args.get("label") or log.eval.task
            label = next((v for k, v in alias.items() if k in fp.stem or k == label), label)
            if variants and label not in variants:
                continue
            for s in log.samples or []:
                if tasks and str(s.id) not in tasks:
                    continue
                rounds, r, subs, turn, first_submit = [], 0, 0, 0, None
                for i, m in enumerate(s.messages):
                    if m.role == "assistant":
                        rounds.append(r)
                        turn += 1
                    elif m.role == "tool" and getattr(m, "function", None) == "submit":
                        subs += 1
                        first_submit = i if first_submit is None else first_submit
                    elif m.role == "user" and (m.text.startswith(FEEDBACK) or m.text.startswith(RECORDED)):
                        r += 1
                score = next(iter(s.scores.values())).value if s.scores else None
                last = s.messages[-1]
                limit = getattr(s, "limit", None)
                if score == "C":
                    end = "passed"
                elif limit is not None and getattr(limit, "type", None) == "message":
                    end = "cut by the message limit"
                elif last.role == "assistant" and not last.tool_calls:
                    end = "stopped (text reply)"
                else:
                    end = "submissions used up or other"
                yield dict(id=f"{fp.stem}|{s.id}|{s.epoch}", variant=label, task=str(s.id), args=args, score=score,
                           end=end, submissions=subs, rejections=r, rounds=rounds, first_submit=first_submit,
                           messages=len(s.messages),
                           turns_after_rejection=sum(1 for x in rounds if x >= 1))


def main():
    argv = sys.argv[1:]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    labels_path = argv[0]
    dirs = argv[argv.index("--logs") + 1:]
    dirs = [d for d in dirs if not d.startswith("--")][: next((i for i, d in enumerate(dirs) if d.startswith("--")), len(dirs))]
    variants = set(opt("--variants").split(",")) if opt("--variants") else None
    tasks = set(opt("--tasks").split(",")) if opt("--tasks") else None
    alias = dict(a.split("=") for a in opt("--alias").split(",")) if opt("--alias") else None
    lab = defaultdict(list)
    for path in labels_path.split(","):
        for l in open(path):
            r = json.loads(l)
            lab[r["episode"]].append(r)
    eps = list(episodes(dirs, None, tasks, alias))
    if variants:
        eps = [e for e in eps if e["variant"] in variants]
    by = defaultdict(list)
    for e in eps:
        us = lab.get(e["id"], [])
        rs = [u for u in us if u["channel"] == "reasoning"]
        rnd = lambda u: e["rounds"][u["turn"]] if u["turn"] < len(e["rounds"]) else 0
        e.update(labelled=bool(us), tokens=sum(u["chars"] for u in rs) / CPT,
                 tokens_after=sum(u["chars"] for u in rs if rnd(u) >= 1) / CPT,
                 new_task=sum(u["label"] == "attempt" and u["new"] and u["target"] == "task" for u in rs),
                 new_check=sum(u["label"] == "attempt" and u["new"] and u["target"] == "check" for u in rs),
                 new_task_after=sum(u["label"] == "attempt" and u["new"] and u["target"] == "task" and rnd(u) >= 1 for u in rs),
                 new_check_after=sum(u["label"] == "attempt" and u["new"] and u["target"] == "check" and rnd(u) >= 1 for u in rs),
                 dc=sum(u["label"] == "doubt_correctness" for u in rs), dl=sum(u["label"] == "doubt_legitimacy" for u in rs),
                 A=sum("A" in u["flags"] for u in us), G=sum("G" in u["flags"] for u in us), S=sum("S" in u["flags"] for u in us))
        by[e["variant"]].append(e)
    out = []
    print("| Variant | Episodes (labelled) | Tasks | Hacked | Ends: passed / cut / stopped / other | Submissions per "
          "episode, median (total) | Turns after 1st rejection per episode, median (total) | New task cand. per 1k "
          "(after 1st rejection) | New check cand. per 1k (after) | Correctness doubts per 1k | Weighing a shortcut "
          "(as labelled) per 1k | A / G / S per 1k |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for v in sorted(by):
        es = by[v]
        le = [e for e in es if e["labelled"]]
        tok, toka = sum(e["tokens"] for e in le), sum(e["tokens_after"] for e in le)
        pk = lambda f, t: 1000 * sum(e[f] for e in le) / t if t else None
        f2 = lambda x: "-" if x is None else f"{x:.2f}"
        ends = [sum(e["end"] == k for e in es) for k in ("passed", "cut by the message limit", "stopped (text reply)",
                                                         "submissions used up or other")]
        row = dict(variant=v, episodes=len(es), labelled=len(le), tasks=sorted({e["task"] for e in es}),
                   first_submit=[e["first_submit"] for e in es],
                   hacked=sum(e["score"] == "C" for e in es), ends=ends,
                   submissions=sum(e["submissions"] for e in es), turns_after=sum(e["turns_after_rejection"] for e in es),
                   submissions_median=median(e["submissions"] for e in es),
                   turns_after_median=median(e["turns_after_rejection"] for e in es),
                   per_episode=[dict(task=e["task"], score=e["score"], end=e["end"], submissions=e["submissions"],
                                     turns_after=e["turns_after_rejection"], messages=e["messages"],
                                     labelled=e["labelled"], tokens=round(e["tokens"]), tokens_after=round(e["tokens_after"]),
                                     **{k: e[k] for k in ("new_task", "new_check", "new_task_after", "new_check_after",
                                                          "dc", "dl", "A", "G", "S")}) for e in es],
                   tokens=round(tok), tokens_after=round(toka),
                   new_task_per_k=pk("new_task", tok), new_task_after_per_k=pk("new_task_after", toka),
                   new_check_per_k=pk("new_check", tok), new_check_after_per_k=pk("new_check_after", toka),
                   dc_per_k=pk("dc", tok), dl_per_k=pk("dl", tok), A_per_k=pk("A", tok), G_per_k=pk("G", tok),
                   S_per_k=pk("S", tok), counts={k: sum(e[k] for e in le) for k in
                                                 ("new_task", "new_check", "new_task_after", "new_check_after", "dc", "dl", "A", "G", "S")})
        out.append(row)
        print(f"| {v} | {len(es)} ({len(le)}) | {len(row['tasks'])} | {row['hacked']}/{len(es)} | {' / '.join(map(str, ends))} | "
              f"{row['submissions_median']:g} ({row['submissions']}) | {row['turns_after_median']:g} ({row['turns_after']}) | "
              f"{f2(row['new_task_per_k'])} ({f2(row['new_task_after_per_k'])}) | "
              f"{f2(row['new_check_per_k'])} ({f2(row['new_check_after_per_k'])}) | {f2(row['dc_per_k'])} | {f2(row['dl_per_k'])} | "
              f"{f2(row['A_per_k'])} / {f2(row['G_per_k'])} / {f2(row['S_per_k'])} |")
    if opt("--json"):
        json.dump(out, open(opt("--json"), "w"), indent=1)


if __name__ == "__main__":
    main()
