"""Precision-corrected weighing a shortcut: L_feedback_none vs L_base (step 3, 5 vs 5 episodes; free first step for
the ACH edit in notes section 7).

    python src/fb_none_check.py sheet   # every labelled weighing (doubt_legitimacy) reasoning unit -> sheet CSV
    python src/fb_none_check.py rates   # after coding: per-episode weighing per 1k, as labelled and corrected

Codes as in src/dl_check.py (W1 on its merits or an open question, W2 only by the rule, R restatement or decision,
C report of conduct, X the shortcut itself, N not about a shortcut). Every unit is read, so there is no sampling error;
one reader, not blind to the labeller's label.
"""
import csv
import json
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, "src")
from step3_compare import exact_p  # noqa: E402

MEAS = "logs/ib_persistence/step3_measures.json"
LAB = sorted(p for p in Path("logs/ib_persistence/labels_step3").glob("*.jsonl") if not p.name.endswith(".raw.jsonl"))
OUT = Path("logs/ib_persistence/dl_check")
SHEET = OUT / "fb_none_vs_base.csv"
CODED = OUT / "fb_none_vs_base_coded.csv"
CPT = 3.0  # as in src/variant_measures.py
VARIANTS = ("L_feedback_none", "L_base")


def episodes():
    """{episode id: variant} for the two variants, from variant_measures' per-episode records (via the log stems)."""
    m = {r["variant"]: r for r in json.load(open(MEAS))}
    return {v: [e["task"] for e in m[v]["per_episode"]] for v in VARIANTS}


def units():
    from variant_measures import episodes as eps  # reads the logs as variant_measures does
    dirs = ["logs/ib_persistence/step3", "logs/ib_cues/round1a", "logs/ib_cues/round1b", "logs/rejection/stage1",
            "logs/rejection/stage1_resume", "logs/effort_pilot"]
    alias = {"V3Vc5HjJdo2d4JeEnJANez": "L_base", "L_recorded": "L_feedback_none"}
    ids = {e["id"]: e["variant"] for e in eps(dirs, set(VARIANTS), None, alias)}
    rows = []
    for p in LAB:
        for l in open(p):
            r = json.loads(l)
            if r["episode"] in ids and r["channel"] == "reasoning":
                rows.append(dict(r, variant=ids[r["episode"]]))
    return ids, rows


def sheet():
    ids, rows = units()
    dl = [r for r in rows if r["label"] == "doubt_legitimacy"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(SHEET, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["idx", "variant", "episode", "turn", "unit", "stance", "text", "code"])
        for i, r in enumerate(sorted(dl, key=lambda r: (r["variant"], r["episode"], r["turn"], r["unit"]))):
            w.writerow([i, r["variant"], r["episode"], r["turn"], r["unit"], r["stance"], " ".join(r["text"].split()), ""])
    print(f"{len(dl)} weighing units in {len(ids)} episodes -> {SHEET}")


def rates():
    ids, rows = units()
    coded = list(csv.DictReader(open(CODED)))
    keep = {(r["episode"], int(r["turn"]), int(r["unit"])) for r in coded if r["code"] in ("W1", "W2")}
    tok, lab, cor = {}, {}, {}
    for e in ids:
        us = [r for r in rows if r["episode"] == e]
        tok[e] = sum(r["chars"] for r in us) / CPT
        lab[e] = sum(r["label"] == "doubt_legitimacy" for r in us)
        cor[e] = sum((r["episode"], r["turn"], r["unit"]) in keep for r in us)
    out = {}
    for v in VARIANTS:
        es = [e for e in ids if ids[e] == v and tok[e] > 0]
        out[v] = dict(episodes=len(es), labelled=sum(lab[e] for e in es), weighing=sum(cor[e] for e in es),
                      tokens=round(sum(tok[e] for e in es)),
                      labelled_k=[round(1000 * lab[e] / tok[e], 3) for e in es],
                      corrected_k=[round(1000 * cor[e] / tok[e], 3) for e in es])
    a, b = out["L_feedback_none"], out["L_base"]
    res = dict(variants=out, codes={c: sum(r["code"] == c for r in coded) for c in ("W1", "W2", "R", "C", "X", "N")},
               labelled_median=(median(a["labelled_k"]), median(b["labelled_k"])), labelled_p=exact_p(a["labelled_k"], b["labelled_k"]),
               corrected_median=(median(a["corrected_k"]), median(b["corrected_k"])),
               corrected_p=exact_p(a["corrected_k"], b["corrected_k"]),
               corrected_pooled=(round(1000 * a["weighing"] / a["tokens"], 3), round(1000 * b["weighing"] / b["tokens"], 3)))
    for v in VARIANTS:
        o = out[v]
        print(f"{v}: {o['episodes']} episodes, {o['labelled']} labelled -> {o['weighing']} weighing; per 1k labelled "
              f"{o['labelled_k']} corrected {o['corrected_k']}")
    print(f"codes {res['codes']}; medians labelled {res['labelled_median']} p {res['labelled_p']:.3f}; corrected "
          f"{res['corrected_median']} p {res['corrected_p']:.3f}; pooled corrected {res['corrected_pooled']}")
    json.dump(res, open(OUT / "fb_none_vs_base.json", "w"), indent=1)


if __name__ == "__main__":
    {"sheet": sheet, "rates": rates}[sys.argv[1]]()
