"""Manifest for her local hand-analysis site (27 Oct, via the orchestrator): every IB chat record behind the IB page
("ImpossibleBench: our runs, four models"), one row per reply or rejection conversation, with metadata and labels only.
The site copies prompts, replies and reasoning from the sources unread; this script reads no reply or reasoning text
itself beyond the reports' own checks (empty visible text, the CONTRA regex on visible text, the code-block test).

    .venv/bin/python src/handview_manifest_ib11.py notes/handview_manifest_ib11.json
    .venv/bin/python src/handview_manifest_ib11.py --check      # counts against the reports' own functions

Included, all four models, every task and rep that exists in finished .eval files (runs in progress are skipped):
- chat arm ("Would it cheat less without a harness?"): logs/ib_chat_vs_harness{,_dsn,_glm,_q27p}/chat plus the 6x3
  top-up's chat re-draws (chat_topup_*), and DeepSeek's earlier SiliconFlow 64k run (logs/ib_chat_vs_harness_ds/chat);
- homework replies: logs/ib_chat_homework/<stem>{,_redraw,_topup_*};
- rejection conversations, one row per try: logs/ib_chat_rejection/<stem>{,_redraw,_topup_*}, with a rounds list
  (round 1 = the homework sample; later rounds = the sample whose model call wrote them; a resumed try's earlier rounds
  point to the try they were kept from);
- Test A's human-grader cells when they exist: logs/ib_chat_grader/<stem>_s*.
Not included (not behind the page): the harness episodes (agent 4's), Qwen 27B's DeepInfra gate run
(logs/ib_chat_vs_harness_q27), the one-call provider checks (step0), DeepSeek's superseded SiliconFlow 64k homework run
(logs/ib_chat_homework/ds_64k_superseded), the harness re-checks (mockllm).

Labels:
- single replies: status usable / missing / error; hacked_registered = code_passes_tests (the stub + find_code's block
  passes the original test file); passes_impossiblebench_scorer = ImpossibleBench's minimal scorer; names_contradiction
  = CONTRA on visible text; missing_cause as the reports (provider error, provider cut, our limit, empty reply);
  hacked_fixed_extraction is null: amendment 8's fixed extraction exists only inside the rejection loop.
- rejection conversations: ended (the report's text, with the missing cause), hacked_round_registered,
  hacked_round_fixed_extraction (amendment 8, or the verifier's isolated re-score for 27B lcbhard_27 r1), per round
  outcome / registered / fixed / names_contradiction / redefines_check, rejection rounds sent without the failing line.
- draw: the dir, the try number for its slot (scored samples in layering order; an Inspect error is not a try), and
  counted = the record the reports count for that slot now (the latest scored one).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PAGE = "ImpossibleBench: our runs, four models"
PAGE_URL = "https://claude.ai/artifact/Ez4fbmxa9Zg5tZdkNpgy2M"
SEC_CHAT = "Would it cheat less without a harness?"
SEC_HW = "Homework framing and autograder rejections"
CH_CHAT = dict(id="ib4-4-chat", title="Without a harness the Qwens still hack; GLM doesn’t and DeepSeek rarely does")
CH_HW = dict(id="ib4-5-homework", title="In her homework framing no model hacks in its first reply, not even the Qwens")
CH_RJ = dict(id="ib4-6-rejection",
             title="Told the autograder failed, GLM and both Qwens start hacking; DeepSeek mostly doesn’t")
V_CHAT = "Chat (DeepSeek: Novita, max 393k)"     # the chart's row label for every model's chat arm
V_CHAT_DS64 = "Chat (DeepSeek: SiliconFlow, 64k)"
V_HW = "Homework (her wording)"
V_RJ = "By round 1 (the homework reply) / By round 2 / By round 3"
SEC_A = "Who asks × who grades (Test A; not on the page yet)"
V_A = {"ta": "Student + human TA", "rv": "Pipeline + human reviewer"}
NAMES = {"qwen": "Qwen 3.8 2.4T", "ds": "DeepSeek V4 Pro", "glm": "GLM 5.2", "q27p": "Qwen 3.8 27B"}
DS_SF64_CHAT = "logs/ib_chat_vs_harness_ds/chat"


def stage_of(d):
    name = d.rstrip("/").rsplit("/", 1)[-1]
    if "topup_" in name:
        return "6x3 top-up " + name.split("topup_")[1]
    if name.endswith("_redraw"):
        return "re-draw (her OK'd re-draws, 26-27 Oct)"
    if d.startswith("logs/ib_chat_grader"):
        return "Test A " + name.split("_", 1)[1]
    if d == DS_SF64_CHAT:
        return "first run (SiliconFlow, max_tokens 64,000)"
    return "first run"


def eval_samples(d):
    """(abs .eval path, sample, model, provider) for the finished .eval files in d, in file order."""
    from inspect_ai.log import read_eval_log
    from costs import provider_of
    p = ROOT / d
    if not p.exists():
        return
    for f in sorted(p.glob("*.eval")):
        if read_eval_log(str(f), header_only=True).status == "started":
            continue
        log = read_eval_log(str(f))
        for s in log.samples or []:
            yield str(f.resolve()), s, log.eval.model, provider_of(log.eval)


def source(path, s):
    return dict(kind="eval", path=path, sample_id=str(s.id), epoch=s.epoch)


def reply_labels(s):
    """Labels of one chat / homework / Test A reply (the reports' rules; metadata and visible-text checks only)."""
    import ib_chat_vs_harness_report as R
    from ib_chat_homework_report import missing_cause, raw_finish
    ev = [e for e in s.events if e.event == "model"]
    e = ev[-1] if ev else None
    out_t = e.output.usage.output_tokens if e is not None and e.output and e.output.usage else None
    max_t = e.config.max_tokens if e is not None and e.config else None
    if s.error or not s.scores:
        return dict(status="error", error=(s.error.message[:200] if s.error else "no score"), hacked_registered=None,
                    hacked_fixed_extraction=None, passes_impossiblebench_scorer=None, names_contradiction=None,
                    missing_cause=None, output_tokens=out_t, max_tokens=max_t, stop_reason=None), max_t
    text = R.final_text(s, "chat")
    end = s.output.stop_reason if s.output else None
    missing = end in R.CUT or not text.strip()
    return dict(status="missing" if missing else "usable",
                hacked_registered=s.scores["code_passes_tests"].value == "C",
                hacked_fixed_extraction=None,
                passes_impossiblebench_scorer=s.scores["scaffold_rule"].value == "C",
                names_contradiction=bool(R.CONTRA.search(text)),
                missing_cause=missing_cause(end, raw_finish(e), out_t, max_t) if missing else None,
                output_tokens=out_t, max_tokens=max_t, stop_reason=end), max_t


def reply_rows(m, dirs, cell, statement, chart, version, page=True, also=None):
    """One row per sample in dirs (layering order), with the try number and whether it is counted now."""
    rows, tries, last = [], defaultdict(int), {}
    for d in dirs:
        for path, s, model, provider in eval_samples(d):
            labels, max_t = reply_labels(s)
            sid = str(s.id)
            _, task, rep = sid.split("|")
            scored = labels["status"] != "error"
            if scored:
                tries[sid] += 1
            row = dict(benchmark="IB", page_title=PAGE if page else None, page_url=PAGE_URL if page else None,
                       statement=statement, chart=chart, version=version, unit=task, unit_kind="task",
                       kind="reply", cell=cell, model=NAMES[m], setup=m, model_id=model, provider=provider, rep=rep,
                       sample_id=sid, labels=labels,
                       draw=dict(dir=d, stage=stage_of(d), try_=tries[sid] if scored else None, counted=False),
                       source=source(path, s))
            if also:
                row["also_shown_in"] = also
            rows.append(row)
            if scored:
                last[sid] = row
    for row in last.values():
        row["draw"]["counted"] = True
    for row in rows:   # "try" is a keyword-ish name in some readers; keep the JSON key plain
        row["draw"]["try"] = row["draw"].pop("try_")
    return rows


def conversation_labels(s):
    """The rejection report's per-sample reading (ib_chat_rejection_report.conversations, one sample)."""
    import ib_chat_vs_harness_report as R
    from inspect_ai.model import ChatMessageAssistant
    from ib_chat_homework_report import blocks, missing_cause, raw_finish
    if s.error or not s.scores:
        return dict(ended="error in rounds 2-3", hacked_round_registered=None, hacked_round_fixed_extraction=None,
                    error=(s.error.message[:200] if s.error else "no score"), rounds=[]), []
    m = s.scores["rejection_outcome"].metadata
    ended = m["ended"]
    if ended == "missing":
        k = m["rounds"][-1]["round"]
        first = (s.metadata or {}).get("resume_at", 2)
        ev = [e for e in s.events if e.event == "model"]
        e = ev[k - first] if len(ev) > k - first else None
        out_t = e.output.usage.output_tokens if e is not None and e.output and e.output.usage else None
        max_t = e.config.max_tokens if e is not None and e.config else None
        ended = f"missing at round {k} (" + missing_cause(m["rounds"][-1].get("end"), raw_finish(e), out_t, max_t) + ")"
    asst = [x for x in s.messages if isinstance(x, ChatMessageAssistant)]
    k = len(m["rounds"])
    no_line = [j + 1 for j in range(1, k) if m.get("extraction", "find_code") == "find_code" and j <= len(asst)
               and blocks(R.visible_text(asst[j - 1]), s.metadata["entry_point"])["scored"] == "text between blocks"]
    rounds = [dict(round=r["round"], outcome=r.get("outcome"), registered=r.get("registered"), fixed=r.get("fixed"),
                   names_contradiction=r.get("names_contradiction"), redefines_check=r.get("redefines_check"))
              for r in m["rounds"]]
    return dict(ended=ended, hacked_round_registered=m["hacked_round"],
                hacked_round_fixed_extraction=m.get("hacked_round_fixed", m["hacked_round"]),
                extraction=m.get("extraction", "find_code"), rejection_without_failing_line_at_rounds=no_line,
                resumed_at_round=(s.metadata or {}).get("resume_at"), rounds=rounds), m["rounds"]


def rejection_rows(m, hw_rows):
    import ib_chat_rejection_report as RJ
    import ib_topup as T
    usable_hw = {r["sample_id"]: r for r in hw_rows if r["labels"]["status"] == "usable" and r["draw"]["counted"]}
    fixed = RJ.VERIFIER_FIXED.get(T.MODELS[m]["stem"], {})
    rows, prev_sources, last = [], {}, {}
    tries = defaultdict(int)
    for d in T.all_dirs(m, "rejection"):
        for path, s, model, provider in eval_samples(d):
            sid = str(s.id)
            key = sid.split("|", 1)[1]
            labels, rec_rounds = conversation_labels(s)
            scored = not (s.error or not s.scores)
            if scored:
                tries[sid] += 1
            if scored and key in fixed and labels.get("extraction") == "find_code" and d == T.existing_dirs(m, "rejection")[0]:
                labels["hacked_round_fixed_extraction"] = fixed[key]["hacked_round_fixed"]
                labels["fixed_extraction_note"] = fixed[key]["note"]
            hw = usable_hw.get((s.metadata or {}).get("round1_id") or f"hw|{key}")
            rounds = [dict(round=1, source=hw["source"] if hw else None, assistant_message=None,
                           note="round 1 = the homework reply; its reasoning is in this homework sample. The rejection "
                                "sample carries it as visible text only (an assistant message in its input).")]
            resume_at = (s.metadata or {}).get("resume_at")
            srcs = {}
            for r in rec_rounds[1:]:
                n = r["round"]
                if resume_at and n < resume_at:
                    srcs[n] = prev_sources.get(sid, {}).get(n)
                    note = (f"kept from an earlier try (this conversation was resumed at round {resume_at}); this "
                            f"sample carries it as visible text only")
                else:
                    srcs[n] = dict(source=source(path, s), assistant_message=n)
                    note = f"assistant message {n} of this sample (model call {n - (resume_at or 2) + 1})"
                src = srcs[n] or {}
                rounds.append(dict(round=n, source=src.get("source"), assistant_message=src.get("assistant_message"),
                                   outcome=r.get("outcome"), note=note))
            if scored:
                prev_sources[sid] = srcs
            task, rep = key.split("|")
            row = dict(benchmark="IB", page_title=PAGE, page_url=PAGE_URL, statement=SEC_HW, chart=CH_RJ, version=V_RJ,
                       unit=task, unit_kind="task", kind="conversation", cell="rejection", model=NAMES[m], setup=m,
                       model_id=model, provider=provider, rep=rep, sample_id=sid, labels=labels,
                       draw=dict(dir=d, stage=stage_of(d), try_=tries[sid] if scored else None, counted=False),
                       rejection_sample=source(path, s), rounds=rounds)
            rows.append(row)
            if scored:
                last[sid] = row
    for row in last.values():
        row["draw"]["counted"] = True
    for row in rows:
        row["draw"]["try"] = row["draw"].pop("try_")
    return rows


def build():
    import ib_grader_cells as G
    import ib_topup as T
    out = []
    for m in T.MODELS:
        out += reply_rows(m, T.all_dirs(m, "chat"), "chat", SEC_CHAT, CH_CHAT, V_CHAT,
                          also=[dict(chart=CH_HW, version="Automated chat, same tasks")])
        if m == "ds":
            out += reply_rows(m, [DS_SF64_CHAT], "chat_siliconflow_64k", SEC_CHAT, CH_CHAT, V_CHAT_DS64)
        hw = reply_rows(m, T.all_dirs(m, "homework"), "homework", SEC_HW, CH_HW, V_HW)
        out += hw
        out += rejection_rows(m, hw)
        for row in reply_rows(m, G.grader_dirs(m), "test_a", SEC_A, None, None, page=False):
            c = row["sample_id"].split("|")[0]
            row.update(cell=c, version=V_A[c])
            out.append(row)
    return out


def check(rows):
    """Counts from the manifest against the reports' own functions (ib_topup's layered states, the chat report on the
    SiliconFlow 64k dir, the rejection report's conversations)."""
    import ib_chat_rejection_report as RJ
    import ib_chat_vs_harness_report as R
    import ib_grader_cells as G
    import ib_topup as T
    ok = True

    def mine(m, cell):
        c = [r for r in rows if r["setup"] == m and r["cell"] == cell and r["draw"]["counted"]]
        use = [r for r in c if r["labels"]["status"] == "usable"]
        return len(use), sum(r["labels"]["hacked_registered"] for r in use), sum(r["labels"]["names_contradiction"] for r in use)
    for m in T.MODELS:
        for cell, st in (("chat", T.chat_state(m)), ("homework", T.homework_state(m))):
            use = [x["final"] for x in st.values() if T.status(x) == "usable"]
            want = (len(use), sum(r["hack"] for r in use), sum(r["points_out"] for r in use))
            got = mine(m, cell)
            ok &= got == want
            print(m, cell, "manifest", got, "report", want, "OK" if got == want else "DIFF")
        g = G.grader_state(m)
        for c in ("ta", "rv"):
            use = [x["final"] for k, x in g.items() if k.startswith(c + "|") and T.status(x) == "usable"]
            want = (len(use), sum(r["hack"] for r in use), sum(r["points_out"] for r in use))
            got = mine(m, c)
            ok &= got == want
            print(m, c, "manifest", got, "report", want, "OK" if got == want else "DIFF")
        conv, _ = RJ.conversations([ROOT / d for d in T.all_dirs(m, "homework")],
                                   [ROOT / d for d in T.all_dirs(m, "rejection")])
        for t, o in RJ.VERIFIER_FIXED.get(T.MODELS[m]["stem"], {}).items():
            if t in conv and conv[t].get("extraction", "find_code") == "find_code":
                conv[t]["hacked_round_fixed"] = o["hacked_round_fixed"]
        rj = {r["sample_id"].split("|", 1)[1]: r for r in rows if r["setup"] == m and r["cell"] == "rejection"
              and r["draw"]["counted"]}
        ran = {k: c for k, c in conv.items() if "rounds" in c and not c["ended"].startswith(("round 1 failed",
                                                                                             "missing at round 1",
                                                                                             "error at round 1",
                                                                                             "hack at round 1"))}
        same = set(rj) == set(ran)
        for k in set(rj) & set(ran):
            a, b = rj[k]["labels"], ran[k]
            same &= a["ended"] == T.how_ended(b) or b["ended"].startswith(a["ended"])
            same &= a["hacked_round_registered"] == b["hacked_round"]
            same &= a["hacked_round_fixed_extraction"] == b.get("hacked_round_fixed", b["hacked_round"])
        ok &= same
        print(m, "rejection", len(rj), "counted conversations vs report", len(ran), "OK" if same else "DIFF")
    ds = R.chat_rows(ROOT / DS_SF64_CHAT)
    use = [r for r in R.best(ds) if not r["error"] and not r["missing"]]
    got = mine("ds", "chat_siliconflow_64k")
    want = (len(use), sum(r["hack"] for r in use), sum(r["points_out"] for r in use))
    ok &= got == want
    print("ds chat_siliconflow_64k manifest", got, "report", want, "OK" if got == want else "DIFF")
    for r in rows:
        srcs = [r["source"]] if "source" in r else [x["source"] for x in r["rounds"]] + [r["rejection_sample"]]
        for x in srcs:
            ok &= x is not None and Path(x["path"]).exists() and x["kind"] == "eval"
    print("every source path exists:", ok)
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    rows = build()
    if sys.argv[1:] == ["--check"]:
        sys.exit(check(rows))
    dest = ROOT / sys.argv[1]
    dest.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    by = defaultdict(int)
    for r in rows:
        by[(r["setup"], r["cell"])] += 1
    print(f"{len(rows)} rows -> {dest}")
    print(dict(by))
