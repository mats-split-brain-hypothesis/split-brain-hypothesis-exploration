"""Fill the SoRH single-turn results from the researcher's 10 prompts to agent 5's 20 (agent 9's request for the
researcher, 2026-10-24), and select the cooperation judge's keys on the 20 afterwards.

  .venv/bin/python src/sorh_fill20.py build      # writes notes/sorh_prereg/fill20_cells.jsonl (texts copied verbatim)
  .venv/bin/python src/sorh_fill20.py coopkeys   # after the fill: notes/coop_study/coop_keys_fill20_<stage>.json

build: for the 26 results-page cells x the 20 prompts, a (cell, prompt) is filled when no sample-0, turn-1 record with
a non-empty reply exists in the screen, realness_step2 or realness_cues records. Its text is copied as it is from
cells.jsonl (plain cells) or realness_cues_cells.jsonl (998d8c9; frame cells). A pair is never filled if a record of
it exists with an empty reply (a reply cut during reasoning is an outcome, not a gap) or if its Qwen call was ever
attempted and cut at max_tokens. Pairs lost to a stop (attempted, no outcome recorded) are filled.

coopkeys: the coop-v1 judge's keys on the 20 prompts for G and the other 7 coop cells (c3b_must, c5_eval,
c7_dont_care, r_student, r_student__c3b_must, r_student__c5_eval, r_student__c7_dont_care): every sample-0,
turn-1 reply with a non-empty reply in screen, realness_step2, realness_cues or fill20 that has no row yet in
logs/sorh_ablation/coop/records.jsonl. Prints counts and keys only, never text.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "notes" / "sorh_prereg"
LOGS = ROOT / "logs" / "sorh_ablation"
PROMPTS = ["sorh_115", "sorh_160", "sorh_164", "sorh_212", "sorh_219", "sorh_223", "sorh_450", "sorh_529", "sorh_553",
           "sorh_559", "sorh_568", "sorh_573", "sorh_580", "sorh_702", "sorh_714", "sorh_743", "sorh_755", "sorh_821",
           "sorh_845", "sorh_931"]
CELLS = ["B", "G", "r_student_noscore", "r_student", "r_checker_noscore", "r_checker", "c2_vague", "c2_vague_more",
         "c5_eval", "c5_training", "c5_real", "c4_auto", "c4_own", "c4_manager", "c3a_exam", "c3a_conv",
         "r_student__c5_eval", "r_student__c5_training", "r_student__c4_auto", "r_student__c4_own",
         "c6_quality_first", "c6_score_first", "c7_dont_care", "r_student__c6_quality_first",
         "r_student__c6_score_first", "r_student__c7_dont_care"]
COOP_CELLS = ["G", "c3b_must", "c5_eval", "c7_dont_care", "r_student", "r_student__c3b_must", "r_student__c5_eval",
              "r_student__c7_dont_care"]
STAGES = ("screen", "realness_step2", "realness_cues")


def jsonl(p):
    return [json.loads(l) for l in p.open() if l.strip()] if p.exists() else []


def records(stages):
    out = []
    for st in stages:
        out += [r for r in jsonl(LOGS / st / "records.jsonl") if r.get("sample") == 0 and r.get("turn", 1) == 1]
    return out


def build():
    recs = records(STAGES)
    have = {(r["cell"], r["prompt_id"]) for r in recs if (r.get("reply") or "").strip()}
    empty = {(r["cell"], r["prompt_id"]) for r in recs if not (r.get("reply") or "").strip()}
    cut = set()
    for st in STAGES:
        for x in jsonl(LOGS / st / "attempts.jsonl"):
            if "|judge" not in x["key"] and x["outcome"] == "length":
                _, cell, pid, _ = x["key"].split("/")
                cut.add((cell, pid))
    texts = {}
    for f in ("cells.jsonl", "realness_cues_cells.jsonl"):
        for r in jsonl(PRE / f):
            texts.setdefault((r["cell"], r["prompt_id"]), r)
    gaps = [(c, p) for p in PROMPTS for c in CELLS if (c, p) not in have]
    held = [g for g in gaps if g in empty or g in cut]
    fill = [g for g in gaps if g not in empty and g not in cut]
    no_text = [g for g in fill if g not in texts]
    print(f"gaps {len(gaps)}; held back (empty-reply record or a length cut): {held}; no registered text: {no_text}")
    if no_text:
        sys.exit("not written: some gaps have no registered text")
    out = PRE / "fill20_cells.jsonl"
    with out.open("w") as f:
        for g in fill:
            f.write(json.dumps(texts[g], ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(ROOT)}: {len(fill)} texts; sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    print("by source:", dict(Counter("cells.jsonl" if "row" in texts[g] else "realness_cues_cells.jsonl"
                                     for g in fill)))
    print("by prompt:", dict(Counter(p for _, p in fill)))


def coopkeys():
    recs = records(STAGES + ("fill20",))
    done = {(x["stage"], x["cell"], x["prompt_id"], x["sample"]) for x in jsonl(LOGS / "coop" / "records.jsonl")}
    keys = sorted({(r["stage"], r["cell"], r["prompt_id"], r["sample"]) for r in recs
                   if r["cell"] in COOP_CELLS and r["prompt_id"] in PROMPTS and (r.get("reply") or "").strip()} - done,
                  key=lambda k: (k[2], k[1], k[0]))
    # one file per source stage: sorh_screen.py coop pairs each keys file with one --source-stage
    for st in sorted({k[0] for k in keys}):
        part = [{"stage": s, "cell": c, "prompt_id": p, "sample": n} for s, c, p, n in keys if s == st]
        out = ROOT / "notes" / "coop_study" / f"coop_keys_fill20_{st}.json"
        out.write_text(json.dumps(part, indent=0))
        print(f"wrote {out.relative_to(ROOT)}: {len(part)} keys; sha256 "
              f"{hashlib.sha256(out.read_bytes()).hexdigest()}")
    print(f"{len(keys)} keys; by cell:", dict(Counter(k[1] for k in keys)), "| by stage:",
          dict(Counter(k[0] for k in keys)))


if __name__ == "__main__":
    {"build": build, "coopkeys": coopkeys}[sys.argv[1]]()
