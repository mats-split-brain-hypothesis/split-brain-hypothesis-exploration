"""Manifest for her local hand-analysis site (27 Oct, via the orchestrator): one row per #4 conversation, metadata only.

    python src/sorh_handview_manifest.py            # #4 (3 prompts x 5) and "#4 Nobody", all four models
    python src/sorh_handview_manifest.py --mt20     # also "#4 on 20 prompts", once the four mt20 runs have ended

Code only: it reads arm, prompt, sample, turn, score_shown and the padding labels, and records where each turn's
record is (file and 1-based line) so the site's builder can copy the conversation unread. It never outputs a reply or
reasoning text. Padding: padding v2 (agent 1's padding_final, the no-output fix file overriding), the page's judge; the
old Luna quality judge alongside. Replies 1 and 2 are shared by a model's arms; their labels come from the cue10_off
original. Written to notes/handview_manifest_sorh4.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sorh_judges as J  # noqa: E402

LOGS = Path("/Users/biancaganescu/Code/split-brain-hypothesis/logs/sorh_ablation")
OUT = ROOT / "notes" / "handview_manifest_sorh4.json"
LABEL = {"cue10_off": "scoring switched off", "cue10_on": "scoring stays on", "cue10_nobody": "nobody will score"}
# model, its #4 stage (off and on), its "Nobody" stage, its 20 x 1 stage (all three arms)
MODELS = [("Qwen 3.8 2.4T", "mt", "mt_nobody_qwen24t", "mt20_qwen24t"),
          ("DeepSeek V4 Pro", "mt_deepseek_64k", "mt_nobody_deepseek", "mt20_deepseek"),
          ("GLM 5.2", "mt_glm52", "mt_nobody_glm52", "mt20_glm52"),
          ("Qwen 3.8 27B", "mt_qwen27b", "mt_nobody_qwen27b", "mt20_qwen27b")]


def jl(p):
    with open(p) as f:
        return [json.loads(l) for l in f if l.strip()]


def v2_labels():
    out = {}
    for fn in ("judged_nometric.jsonl", "judged_nometric_nooutput_fix.jsonl"):
        p = LOGS / "padding_final" / fn
        if p.exists():
            for r in jl(p):
                st, line = r["key"].split("/")[0], int(r["key"].split("/")[1])
                out[(st, line)] = r["padding_final_nometric"]
    return out


def turns(stage, arms, v2):
    """{(arm, prompt_id, sample): {turn: (path, line, record metadata)}} for one stage's records file."""
    path = LOGS / stage / "records.jsonl"
    by = {}
    with open(path) as f:
        n = 0
        for raw in f:
            if not raw.strip():
                continue
            n += 1  # the line number among non-empty lines; records files have no blank lines (checked below)
            r = json.loads(raw)
            if r["arm"] not in arms:
                continue
            meta = {"score_shown": r.get("score_shown"), "v2": v2.get((stage, n)),
                    "old": J.parse_quality((r.get("judge") or {}).get("quality"))["padded"]}
            by.setdefault((r["arm"], r["prompt_id"], r["sample"]), {})[r["turn"]] = (str(path), n, meta)
    with open(path) as f:
        assert all(l.strip() for l in f), f"blank line in {path}: line numbers would be off"
    return by


def rows_for(model, statement, convs, shared_from):
    """One row per conversation. shared_from: the conversations whose turns 1-2 hold the original shared replies."""
    out = []
    for (arm, pid, s), t in sorted(convs.items(), key=lambda kv: (kv[0][1], kv[0][2], list(LABEL).index(kv[0][0]))):
        orig = shared_from[("cue10_off", pid, s)]
        lab = lambda turn, k: (orig if turn <= 2 else t).get(turn, (None, None, {}))[2].get(k)
        out.append({
            "benchmark": "SoRH", "statement": statement, "unit": pid, "version": arm, "version_label": LABEL[arm],
            "model": model, "rep": s, "turns": len(t), "complete": sorted(t) == [1, 2, 3, 4, 5],
            "labels": {
                "padded_v2": {"r1": lab(1, "v2"), "r2": lab(2, "v2"), "final": lab(5, "v2")},
                "padded_old": {"r1": lab(1, "old"), "r2": lab(2, "old"), "final": lab(5, "old")},
                "score_shown": {str(k): t[k][2]["score_shown"] for k in sorted(t)},
            },
            "source": [{"path": t[k][0], "line": t[k][1], "turn": k} for k in sorted(t)],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mt20", action="store_true", help='add "#4 on 20 prompts" (after the four mt20 runs end)')
    a = ap.parse_args()
    v2 = v2_labels()
    rows = []
    for model, seed, nob, mt20 in MODELS:
        pair = turns(seed, ("cue10_off", "cue10_on"), v2)
        rows += rows_for(model, "#4", pair, pair)
        rows += rows_for(model, "#4 Nobody", turns(nob, ("cue10_nobody",), v2), pair)
        if a.mt20:
            three = turns(mt20, tuple(LABEL), v2)
            rows += rows_for(model, "#4 on 20 prompts", three, three)
    about = {
        "what": "Her hand-analysis site, SoRH #4: one row per conversation, metadata only (no reply or reasoning text).",
        "source": "each turn's record: path of the records.jsonl file and its 1-based line; turns 1-2 of the stays-on "
                  "and nobody arms are copies of the cue10_off originals (same reply and reasoning, copied_from set)",
        "padded_v2": "padding version 2 (the page's judge): agent 1's padding_final, no metric, final output; the "
                     "no-output fix file overrides; null = no label (e.g. an excluded or unreached turn)",
        "padded_old": "the Luna quality judge's padded, as first reported",
        "r1_r2": "replies 1 and 2 are shared by a model's arms; labels taken from the cue10_off original",
        "score_shown": "per turn, the score in that turn's message (the previous reply's cue-8 score); null where "
                       "no score is shown (turn 1, and turns 3-5 of switched off and nobody)",
        "complete": "false where a turn is missing (an excluded call, or a stays-on arm stopped on an unparsed count)",
        "script": "src/sorh_handview_manifest.py" + (" --mt20" if a.mt20 else ""),
    }
    OUT.write_text(json.dumps({"about": about, "rows": rows}, indent=1, ensure_ascii=False) + "\n")
    by = {}
    for r in rows:
        by.setdefault((r["statement"], r["model"]), [0, 0])
        by[(r["statement"], r["model"])][0] += 1
        by[(r["statement"], r["model"])][1] += not r["complete"]
    for k, (n, inc) in by.items():
        print(f"{k[0]:18} {k[1]:16} {n} conversations, {inc} incomplete")
    print(f"{len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
