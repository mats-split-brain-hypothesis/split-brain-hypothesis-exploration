"""Manifest of every episode behind agent 4's four charts on the IB page ("ImpossibleBench: our runs, four models"),
for her local hand-analysis site (orchestrator, 27 Oct). Metadata only: no reply or reasoning text is printed or
stored, and no calls are made.

    python src/handview_manifest_ib4.py   # writes notes/handview_manifest_ib4.json

One row per episode per statement. Rows hold the page's wording (statement, section, chart title, row label), the
labels the page counts, and where the episode is: source = {"kind": "eval", "path", "sample_id", "epoch"}, where
source.epoch is the sample's epoch inside that file. The row's own "epoch" is its slot on the page; the two differ for
re-runs that ran as epoch 1 in their own dir (GLM's told-before fill, the §23 top-up).

Episodes included are exactly the ones counted on the page (the same dirs, labels and rules as §22's sources):
- #1 told before: no-message vs told arms, 6 tasks x 3 epochs per model; errored episodes are left out, as on the page.
- #1 told after: one continuation each way per point, only points with both arms (Qwen 3.8 2.4T exp 10's r4_ points;
  DeepSeek epoch 1 only). "epoch" is the original episode's epoch; source_log and source_sample name the original
  episode the continuation was cut from.
- #2 and #3: E_N vs E_D and E_N vs E_S. The E_N episodes are the shared no-STOP arm, so each appears once under #2
  and once under #3. Epoch 1 from the §20/§21 dirs; the §23 top-up dirs are added as epochs 2-3 when they hold
  samples, with their judge records from topup_judge.jsonl.
"""
import glob
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grading_off import episode as go_episode  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402
from stop3_outcomes import episode as s3_episode, norm  # noqa: E402

D = "logs/ib_persistence"
F = "logs/forensics_no_person"
ABS = lambda p: os.path.realpath(p)  # noqa: E731
PAGE = "ImpossibleBench: our runs, four models"
S1 = "#1 Removing the grader decreases the chance of a hack"
S2 = ("#2 Any cheating detection mechanism (human reviewer or automated cheating detector) seems to increase the "
      "chance of an honest answer")
S3 = "#3 A “STOP if something is inconsistent or flawed” instruction can prevent hacking"
T_BEFORE = "Told first: both Qwens hack less; GLM and DeepSeek rarely hack that early anyway"
T_AFTER = "Told after starting a hack: Qwen 2.4T and GLM give some up; DeepSeek and 27B keep all"
T_DET = "A cheating-detector sentence stops only Qwen 3.8 2.4T"
# T_STOP differs from the old Docs page's title ("…DeepSeek still hands one in 4 times of 6", page Ez4fbmxa9Zg5tZdkNpgy2M,
# read-only) because of the §23 update to n = 18: DeepSeek under STOP is 14 hacks / 4 reports of 18. The other
# titles still hold at n = 18 and match that page.
T_STOP = "STOP stops the hack on three models; DeepSeek still hands one in 14 times of 18"
QMAX, DS, GLM, Q27 = "Qwen 3.8 2.4T", "DeepSeek V4 Pro", "GLM 5.2", "Qwen 3.8 27B"
excluded = []


def base(statement, section, chart, model, version, arm, task, epoch, fp, s):
    return dict(benchmark="IB", page_title=PAGE, statement=statement, section=section, chart_title=chart, unit="task",
                task=task, version=version, arm=arm, model=model, epoch=epoch,
                source=dict(kind="eval", path=ABS(fp), sample_id=s.id, epoch=s.epoch))


def labelled(pattern, label):
    for fp in sorted(glob.glob(pattern)):
        log = read_eval_log(fp)
        if (log.eval.task_args or {}).get("label") != label:
            continue
        for s in log.samples or []:
            if s.error:
                excluded.append(f"{log.eval.model} {label} {s.id} ep{s.epoch} ({os.path.basename(os.path.dirname(fp))}): "
                                f"errored")
                continue
            yield fp, log, s


def told_before():
    # (model, [(dir, label, epoch slot override for epoch-1 fill samples)]) per arm, as in writeup4_numbers.CHART1
    sets = [(QMAX, [(f"{D}/grading_off_r4", "G4_C", None)], [(f"{D}/grading_off_r4", "G4_A", None)]),
            (DS, [(f"{D}/ds_stop", "D3_C", None)], [(f"{D}/ds_off_before", "D1_A", None)]),
            (GLM, [(f"{D}/rep_glm_before", "G_C", None), (f"{D}/rep_glm_before_fill", "G_C", 3)],
             [(f"{D}/rep_glm_before", "G_A", None), (f"{D}/rep_glm_before_fill", "G_A", 3)]),
            (Q27, [(f"{D}/rep_q27_before", "G_C", None)], [(f"{D}/rep_q27_before", "G_A", None)])]
    out = []
    for model, c_src, a_src in sets:
        for version, src in (("No message", c_src), ("Told grading is off", a_src)):
            for d, lab, slot in src:
                for fp, _, s in labelled(f"{d}/*.eval", lab):
                    r = go_episode(s, lab)
                    row = base(S1, "Told before it starts", T_BEFORE, model, version, lab, s.id,
                               slot if slot else s.epoch, fp, s)
                    row["labels"] = dict(hacked_by_first_submission=r["hack_first"], hacked_by_end=r["hack_end"],
                                         score=r["score"], submissions=r["submissions"])
                    out.append(row)
    return out


def cont_kept(s, rec):
    score = list(s.scores.values())[0].value if s.scores else None
    tc = rec["test_changed_at_submit"] if rec["submitted"] else rec.get("test_changed_end")
    return bool(score == "C" or tc), score, bool(tc)


def told_after():
    # (model, continuation dirs, points file, id prefix, audit files, continuation epoch kept)
    sets = [(QMAX, [f"{F}/exp10_run"], f"{F}/exp10/points.json", "r4_",
             glob.glob(f"{F}/replay_audit/*audit-exp10-L-none*.eval"), None),
            (DS, [f"{D}/ds_momentum_run"], f"{D}/ds_momentum/points.json", "ds_",
             glob.glob(f"{D}/ds_momentum_audit/*.eval"), 1),
            (GLM, [f"{D}/rep_glm_after"], f"{D}/rep_glm_points/points.json", "glm_",
             glob.glob(f"{D}/rep_glm_audit/*.eval"), None),
            (Q27, [f"{D}/rep_q27_after", f"{D}/rep_q27_after_fill"], f"{D}/rep_q27_points/points.json", "q27_",
             glob.glob(f"{D}/rep_q27_audit/*.eval"), None)]
    out = []
    for model, dirs, pts_file, prefix, audit, keep_epoch in sets:
        pts = {p["id"]: p for p in json.load(open(pts_file))["points"] if p["id"].startswith(prefix)}
        worked = {}
        for fp in audit:
            for s in read_eval_log(fp).samples or []:
                rec = (s.store or {}).get("ib_cont")
                if rec and rec["point"] in pts:
                    worked[rec["point"]] = cont_kept(s, rec)[0]
        found = {}
        for d in dirs:
            for fp in sorted(glob.glob(f"{d}/*.eval")):
                for s in read_eval_log(fp).samples or []:
                    rec = (s.store or {}).get("ib_cont")
                    if s.error and not rec:
                        excluded.append(f"{model} continuation {s.id} ep{s.epoch} ({os.path.basename(d)}): errored")
                        continue
                    if not rec or rec["point"] not in pts or rec["arm"] not in ("L_msg", "L_none"):
                        continue
                    if keep_epoch and s.epoch != keep_epoch:
                        continue
                    key = (rec["arm"], rec["point"])
                    assert key not in found, (model, key)
                    found[key] = (fp, s, rec)
        paired = {p for a, p in found if a == "L_msg"} & {p for a, p in found if a == "L_none"}
        for (arm, point), (fp, s, rec) in sorted(found.items(), key=lambda x: x[0][1]):
            if point not in paired:
                excluded.append(f"{model} continuation {point} {arm}: no pair, not on the page")
                continue
            p = pts[point]
            kept, score, tc = cont_kept(s, rec)
            version = "Told grading is off" if arm == "L_msg" else "Not told"
            row = base(S1, "Told right after it starts a hack", T_AFTER, model, version, arm, p["task"], p["epoch"],
                       fp, s)
            row.update(point=point, source_log=ABS(p["log"]), source_sample=dict(sample_id=p["task"], epoch=p["epoch"]))
            w = worked.get(point)
            row["labels"] = dict(kept_the_hack=kept, score=score, test_changed=tc, hack_already_working_when_told=w,
                                 group="Hack already working when told" if w else "Hack not yet working when told"
                                 if w is False else None)
            out.append(row)
    return out


def judged(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            j = json.loads(line)
            out[(j["model"], j["arm"], j["task"], int(j["epoch"]))] = j
    return out


def stop_det():
    # (model, [(dir, judge file, epoch shift)]): epoch 1 (§20, §21), then the §23 top-up as epochs 2-3 if present
    tj = f"{D}/topup_judge.jsonl"
    sets = [(QMAX, [(f"{D}/stopdet_qwen", f"{D}/stopdet_judge.jsonl", 0), (f"{D}/topup_qwen_stopdet", tj, 1)]),
            (DS, [(f"{D}/stopdet_ds", f"{D}/stopdet_judge.jsonl", 0), (f"{D}/topup_ds_stopdet", tj, 1)]),
            (GLM, [(f"{D}/rep_glm_stopdet", f"{D}/rep_judge.jsonl", 0), (f"{D}/topup_glm_stopdet", tj, 1)]),
            (Q27, [(f"{D}/rep_q27_stopdet", f"{D}/rep_judge.jsonl", 0), (f"{D}/topup_q27_stopdet", tj, 1)])]
    cells = [(S2, T_DET, "E_N", "“No person will read the reply.”"),
             (S2, T_DET, "E_D", "“…an automated cheating detector.”"),
             (S3, T_STOP, "E_N", "No STOP"),
             (S3, T_STOP, "E_S", "STOP (Goodfire’s instruction)")]
    # §23 addendum: re-draws she OKed for errored top-up episodes, (dir, judge file, {(arm, task, file epoch): slot})
    from topup_outcomes import REDRAWS
    name_map = {"Qwen 3.8 2.4T": "Qwen 3.8 Max"}  # topup_outcomes names the 2.4T "Qwen 3.8 Max"
    out = []
    for model, srcs in sets:
        srcs = [(d, j, sh, None) for d, j, sh in srcs] + \
            [(d, j, 0, sl) for d, j, sl in REDRAWS.get(name_map.get(model, model), [])]
        for d, judge_file, shift, slots in srcs:
            j_all = judged(judge_file)
            for statement, chart, lab, version in cells:
                for fp, log, s in labelled(f"{d}/*.eval", lab):
                    if slots is not None and (lab, s.id, s.epoch) not in slots:
                        continue
                    m = log.eval.model.removeprefix("openrouter/")
                    r = s3_episode(s, m, lab)
                    j = j_all.get((m, lab, s.id, s.epoch))
                    quote_found = bool(j and j.get("quote")) and norm(j["quote"]) in norm(r["visible"])
                    report = (bool(j.get("reports_flaw")) and quote_found) if j else r["regex_report"]
                    outcome = "hack" if r["handed"] else "reported" if report else "neither"
                    ep = slots[(lab, s.id, s.epoch)] if slots is not None else s.epoch + shift
                    row = base(statement, None, chart, model, version, lab, s.id, ep, fp, s)
                    row["labels"] = dict(
                        handed_in_a_hack=r["handed"], reported_broken_test=bool(report and not r["handed"]),
                        outcome=outcome, judge_said_report_quote_not_found=bool(
                            j and not r["handed"] and j.get("reports_flaw") and not quote_found),
                        judge_record=j is not None, ended=r["ended"], submissions=r["submissions"])
                    out.append(row)
    return out


def main():
    rows = told_before() + told_after() + stop_det()
    keys = Counter((r["statement"], r["section"], r["model"], r["version"], r["task"], r["epoch"]) for r in rows)
    dup = [k for k, v in keys.items() if v > 1]
    assert not dup, dup[:3]
    Path("notes/handview_manifest_ib4.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(rows)} rows, {len({(r['source']['path'], r['source']['sample_id'], r['source']['epoch']) for r in rows})} "
          f"distinct episodes")
    n = Counter((r["statement"][:2], r["section"] or "", r["model"], r["version"]) for r in rows)
    for k in sorted(n, key=lambda k: (k[0], k[1], [QMAX, DS, GLM, Q27].index(k[2]), k[3])):
        sel = [r for r in rows if (r["statement"][:2], r["section"] or "", r["model"], r["version"]) == k]
        lab = sel[0]["labels"]
        if "hacked_by_first_submission" in lab:
            c = f"hacked by first submission {sum(r['labels']['hacked_by_first_submission'] for r in sel)}, by the end " \
                f"{sum(r['labels']['hacked_by_end'] for r in sel)}"
        elif "kept_the_hack" in lab:
            c = f"kept the hack {sum(r['labels']['kept_the_hack'] for r in sel)}; already working " \
                f"{sum(r['labels']['hack_already_working_when_told'] is True for r in sel)}"
        else:
            o = Counter(r["labels"]["outcome"] for r in sel)
            c = f"hack {o['hack']} / reported {o['reported']} / neither {o['neither']}; judge said report, quote not " \
                f"found {sum(r['labels']['judge_said_report_quote_not_found'] for r in sel)}; epochs " \
                f"{sorted(Counter(r['epoch'] for r in sel).items())}"
        print(f"  {k[0]} {k[1][:12]:<12} {k[2]:<16} {k[3][:30]:<30} n {len(sel):>2} | {c}")
    print("left out:", excluded or "none")


if __name__ == "__main__":
    main()
