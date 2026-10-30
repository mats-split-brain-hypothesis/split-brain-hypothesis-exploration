"""DeepSeek V4 Pro replication of her SoRH single-turn conclusions #1, #2, #3 and #5 (notes/sorh_deepseek20_design.md).

build:   notes/sorh_prereg/deepseek20_cells.jsonl, the 20 cells x her 20 prompts. Each text is the one Qwen's first
         sample got (logs/sorh_ablation/{screen, screen_topup, fill20, realness_cues, realness_step2}), checked against
         the cells file it came from; row and b_text from the prompt's registered B (cells.jsonl).
analyse: notes/sorh_deepseek20_results.md, padded k/n per cell for Qwen (first sample per prompt, as the orchestrator's
         recount) and DeepSeek (all 400 from deepseek20_64k, amendment 1), grouped by her headings.
Run from the worktree root."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "notes" / "sorh_prereg"
sys.path.insert(0, str(ROOT / "src"))
import sorh_judges as J  # noqa: E402
import sorh_screen as S  # noqa: E402

# Her headings (verbatim, orchestrator's map b4ead91) and the cells each rests on
HEADINGS = [
    ("#1 A stated score is enough to make Qwen game it, regardless of whether the model reads the conversation as "
     "real or eval", ["B", "G", "r_student", "r_student__c5_eval", "r_student__c5_training"]),
    ("#2 The score has to be named explicitly to be pursued, the model doesn't verbalise a scoring function otherwise",
     ["c3a_exam", "c3a_conv", "c2_vague"]),
    ("#3 As long as there is an explicit scoring function, the setup or who requests it doesn't matter",
     ["c4_auto", "c4_own", "c4_manager", "c5_training", "c5_eval", "c5_real"]),
    ("#5 If the user states different or conflicting priorities with the score, the model focuses on the user's "
     "priorities", ["G", "c6_quality_first", "c7_dont_care", "c6_score_first", "r_student", "r_student__c6_quality_first",
                    "r_student__c7_dont_care", "r_student__c6_score_first"])]
CELLS = list(dict.fromkeys(c for _, cs in HEADINGS for c in cs))  # 20
QWEN_STAGES = ["screen", "screen_topup", "fill20", "realness_cues", "realness_step2"]
SOURCE_FILES = ["cells.jsonl", "fill20_cells.jsonl", "realness_cues_cells.jsonl", "realness_step2_cells.jsonl",
                "screen_topup_cells.jsonl"]
OUT = PRE / "deepseek20_cells.jsonl"


def jl(path):
    return [json.loads(l) for l in Path(path).open() if l.strip()]


def qwen_first():
    """(cell, prompt_id) -> Qwen's first-sample record over the source stages (lowest sample, then stage order)."""
    first = {}
    for st in QWEN_STAGES:
        for r in jl(ROOT / "logs/sorh_ablation" / st / "records.jsonl"):
            k = (r["cell"], r["prompt_id"])
            if r["cell"] in CELLS and (k not in first or r["sample"] < first[k][1]["sample"]):
                first[k] = (st, r)
    return first


def build():
    first = qwen_first()
    reg_b = {r["prompt_id"]: r for r in jl(PRE / "cells.jsonl") if r["cell"] == "B"}
    prompts = sorted(reg_b)
    assert len(prompts) == 20 and set(S.HER10) <= set(prompts), prompts
    assert set(S.HER10) == {r["prompt_id"] for r in jl(PRE / "cells_10.jsonl")}
    files = {f: {(r["cell"], r["prompt_id"]): r["text"] for r in jl(PRE / f)} for f in SOURCE_FILES}
    rows = []
    for c in CELLS:
        for p in prompts:
            st, r = first[(c, p)]
            src = [f for f in SOURCE_FILES if files[f].get((c, p)) == r["prompt"]]
            assert src, (c, p)
            rows.append({"cell": c, "prompt_id": p, "row": reg_b[p]["row"], "b_text": reg_b[p]["text"],
                         "text": r["prompt"], "qwen_stage": st, "source_file": src[0]})
    assert len(rows) == 400 and len({(r["cell"], r["prompt_id"]) for r in rows}) == 400
    assert all(r["text"] == r["b_text"] for r in rows if r["cell"] == "B")
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows, sha256 {hashlib.sha256(OUT.read_bytes()).hexdigest()}")


def padded_of(r):
    """True/False from the quality judge; None if unparsed or cut during reasoning (a7d6e9f: reply measures missing)."""
    if r.get("finish") == "length" and not (r.get("reply") or "").strip():
        return None
    return J.parse_quality((r.get("judge") or {}).get("quality"))["padded"]


def analyse(records=None, out=None):
    qwen = {k: padded_of(r) for k, (_, r) in qwen_first().items()}
    # amendment 1: all 400 from the fresh 64k run; deepseek_bg and the 22 paused deepseek20 records are not used
    new = Path(records) if records else ROOT / "logs/sorh_ablation/deepseek20_64k/records.jsonl"
    ds_recs = jl(new) if new.exists() else []
    ds = {(r["cell"], r["prompt_id"]): padded_of(r) for r in ds_recs if r["sample"] == 0}
    prompts = sorted({p for _, p in qwen})

    def kn(d, c):
        v = [d.get((c, p)) for p in prompts]
        ok = [x for x in v if x is not None]
        return f"{sum(ok)}/{len(ok)}" + ("" if len(ok) == 20 else f" ({20 - len(ok)} missing)")

    ct = lambda r: (r.get("usage") or {}).get("completion_tokens") or 0
    max_stop = max((ct(r) for r in ds_recs if r.get("finish") == "stop"), default=0)
    n32 = sum(r.get("finish") == "length" and ct(r) == 32768 for r in ds_recs)
    n_over = sum(r.get("finish") == "stop" and ct(r) > 64000 for r in ds_recs)
    n64 = sum(r.get("finish") == "length" and ct(r) >= 64000 and not (r.get("reply") or "").strip() for r in ds_recs)
    lines = ["# DeepSeek V4 Pro next to Qwen: her SoRH single-turn conclusions (padded k/n)", "",
             "Generated by `src/sorh_deepseek20.py analyse`. Design: notes/sorh_deepseek20_design.md. One reply per "
             "prompt per cell on her 20 prompts; padded is the quality judge's padding flag. Qwen: the first sample "
             "per prompt (the orchestrator's recount; max_tokens 24,000). DeepSeek: all 400 from deepseek20_64k "
             "(max_tokens 64,000, amendment 1). A reply cut during reasoning counts as missing (a7d6e9f). SiliconFlow "
             f"capped some calls at 32,768, below the requested 64,000 ({n32} here), while others ran longer (in this "
             f"run, replies finished up to {max_stop:,} completion tokens; {n64} reasoned through the full 64,000 "
             "without answering). So whether a long reply was cut depends partly on which kind of call it landed on. "
             f"{n_over} replies finished with stop past the requested 64,000 (as in the 24k runs: deepseek_bg, and "
             "agent 3's 33,937 and 38,112 today). This sentence was corrected after the results were read: the "
             "earlier fixed text said calls past the requested limit were seen only in the 24k runs.", ""]
    for head, cs in HEADINGS:
        lines += [f"## {head}", "", "| cell | Qwen | DeepSeek V4 Pro |", "|---|---|---|"]
        lines += [f"| {c} | {kn(qwen, c)} | {kn(ds, c)} |" for c in cs]
        lines.append("")
    cuts = sorted((r["cell"], r["prompt_id"], (r.get("usage") or {}).get("completion_tokens"),
                   "cut in the answer, kept and judged" if (r.get("reply") or "").strip()
                   else "cut during reasoning, missing") for r in ds_recs if r.get("finish") == "length")
    lines += ["## DeepSeek replies that hit a token limit", "",
              "As registered (a7d6e9f), and as for Qwen's 4 first samples cut in the answer: a reply cut during "
              "reasoning is missing; a reply cut in the answer is kept, its padded flag judged on the cut text.", ""]
    lines += [f"- {c}/{p}: {t} completion tokens, {how}" for c, p, t, how in cuts] or ["- none"]
    # Reply calls that failed with a provider error (finish error, connection closed, JSON error in the stream) are
    # retried up to 3 times (length cuts never); a job with no record after 3 failures is missing
    att = new.parent / "attempts.jsonl"
    failed_keys = {tuple(a["key"].split("/")[1:3]) for a in (jl(att) if att.exists() else [])
                   if "|" not in a["key"] and a["outcome"] not in ("ok", "length")}
    have = {(r["cell"], r["prompt_id"]) for r in ds_recs}
    lost = sorted(f"{c}/{p}" for c, p in failed_keys if (c, p) not in have)
    lines += ["", f"Reply calls retried after a provider error: {len(failed_keys)} jobs; "
              f"{len(failed_keys & have)} got a record on a later attempt; no record (missing): "
              + (", ".join(lost) or "none") + ". If long streams fail more often, these retries and losses also lean "
              "toward shorter replies.", ""]
    import statistics
    med ={c: statistics.median([ct(r) for r in ds_recs if r["cell"] == c]) for c in CELLS
           if any(r["cell"] == c for r in ds_recs)}
    cut_cells = sorted({c for c, _, _, _ in cuts}, key=lambda c: -med.get(c, 0))
    lines += ["", "**Direction (the verifier):** the cuts fall on the replies that reason longest, which are in the "
              "score cells, so the k/n there may undercount padding (as the orchestrator's question to her put it: "
              "\"Counted as missing, that undercounts gaming\"). Median DeepSeek completion tokens, cells with a cut: "
              + (", ".join(f"{c} {med[c]:,.0f}" for c in cut_cells) or "none")
              + f"; all cells {statistics.median([ct(r) for r in ds_recs] or [0]):,.0f}.", ""]
    unparsed = sorted(f"{r['cell']}/{r['prompt_id']}" for r in ds_recs
                      if J.parse_count((r.get("judge") or {}).get("count"), r["row"], r.get("reply") or "")["status"]
                      == "unparsed")
    lines += ["Count judge unparsed (e.g. cut at its 3,000-token limit; not used here, padded comes from the quality "
              "judge): " + (", ".join(unparsed) or "none"), ""]
    out = Path(out) if out else ROOT / "notes" / "sorh_deepseek20_results.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}: DeepSeek {len(ds)} records, Qwen {len(qwen)}")


# Her "replicate everything of SORH … on GLM 5.2 and Qwen 3.8 27B" (notes/sorh_models20_design.md)
MODELS = [("DeepSeek V4 Pro", "deepseek20_64k", "deepseek/deepseek-v4-pro"),
          ("GLM 5.2", "glm52_20", "z-ai/glm-5.2"),
          ("Qwen 3.8 27B", "qwen27b_20", "qwen/qwen3.8-27b")]
LEN_CHECK = [("c3a_exam", "sorh_529"), ("r_student__c5_eval", "sorh_559")]  # DeepSeek's two longest (107.6k, 85.9k)


def build_lencheck():
    rows = {(r["cell"], r["prompt_id"]): r for r in jl(OUT)}
    out = PRE / "len_check_cells.jsonl"
    out.write_text("".join(json.dumps(rows[k], ensure_ascii=False) + "\n" for k in LEN_CHECK))
    print(f"wrote {out.relative_to(ROOT)}: {len(LEN_CHECK)} rows, sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


def lencheck(stage, root=None):
    """The length check's numbers only (finish, tokens, characters, provider, cost); no text is printed."""
    base = Path(root) if root else ROOT / "logs/sorh_ablation"
    for r in jl(base / stage / "records.jsonl"):
        u = r.get("usage") or {}
        rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
        print(f"{r['cell']}/{r['prompt_id']}: model {r['model']}, provider {r['provider']}, finish {r['finish']}, "
              f"completion tokens {u.get('completion_tokens')}, reasoning tokens {rt}, reasoning chars "
              f"{len(r.get('reasoning') or '')}, reply chars {len(r.get('reply') or '')}, {r['seconds']:.0f} s, "
              f"${float(u.get('cost') or 0):.4f}")


def analyse_all(root=None, out=None):
    """Padded k/n per cell for Qwen 3.8 2.4T and the three replication models, plus each model's cuts and losses."""
    import statistics
    base = Path(root) if root else ROOT / "logs/sorh_ablation"
    qwen = {k: padded_of(r) for k, (_, r) in qwen_first().items()}
    prompts = sorted({p for _, p in qwen})
    ct = lambda r: (r.get("usage") or {}).get("completion_tokens") or 0

    def kn(d, c):
        ok = [x for x in (d.get((c, p)) for p in prompts) if x is not None]
        return f"{sum(ok)}/{len(ok)}" + ("" if len(ok) == 20 else f" ({20 - len(ok)} missing)")

    cols, notes = [], []
    for label, stage, model in MODELS:
        path = base / stage / "records.jsonl"
        recs = jl(path) if path.exists() else []
        assert all(r["model"] == model and r["sample"] == 0 for r in recs), stage
        cols.append((label, {(r["cell"], r["prompt_id"]): padded_of(r) for r in recs}))
        cuts = sorted((r["cell"], r["prompt_id"], ct(r), "cut in the answer, kept and judged"
                       if (r.get("reply") or "").strip() else "cut during reasoning, missing")
                      for r in recs if r.get("finish") == "length")
        att = path.parent / "attempts.jsonl"
        failed = {tuple(a["key"].split("/")[1:3]) for a in (jl(att) if att.exists() else [])
                  if "|" not in a["key"] and a["outcome"] not in ("ok", "length")}
        have = {(r["cell"], r["prompt_id"]) for r in recs}
        lost = sorted(f"{c}/{p}" for c, p in failed if (c, p) not in have)
        med = {c: statistics.median([ct(r) for r in recs if r["cell"] == c]) for c in {x[0] for x in cuts}}
        unparsed = sum(J.parse_count((r.get("judge") or {}).get("count"), r["row"], r.get("reply") or "")["status"]
                       == "unparsed" for r in recs)
        notes += [f"## {label} ({stage}): {len(recs)} records", "",
                  f"- Longest reply finished with stop: {max((ct(r) for r in recs if r.get('finish') == 'stop'), default=0):,}"
                  f" completion tokens; {sum(r.get('finish') == 'stop' and ct(r) > 64000 for r in recs)} finished past "
                  f"the requested 64,000; {sum(r.get('finish') == 'length' and ct(r) < 64000 for r in recs)} cut below it.",
                  "- Token-limit cuts (a reply cut during reasoning is missing; one cut in the answer is kept and "
                  "judged, as for Qwen's 4):"]
        notes += [f"  - {c}/{p}: {t:,} completion tokens, {how}" for c, p, t, how in cuts] or ["  - none"]
        notes += [f"- Reply calls retried after a provider error or an empty reply (both logged as 'error'; label corrected after the results were read): {len(failed)} jobs; {len(failed & have)} got a record "
                  f"later; no record (missing): {', '.join(lost) or 'none'}. If long streams fail more often, these "
                  "lean toward shorter replies.",
                  "- Direction: cuts fall on the longest replies, so the k/n in cells with a cut may undercount padding. "
                  "Median completion tokens in those cells: " + (", ".join(f"{c} {v:,.0f}" for c, v in
                                                                     sorted(med.items(), key=lambda x: -x[1])) or "none")
                  + f"; all cells {statistics.median([ct(r) for r in recs] or [0]):,.0f}.",
                  f"- Count judge unparsed (not used; padded comes from the quality judge): {unparsed}.", ""]
    lines = ["# Her SoRH single-turn conclusions on four models (padded k/n)", "",
             "Generated by `src/sorh_deepseek20.py analyse_all`. Designs: notes/sorh_deepseek20_design.md (DeepSeek) and "
             "notes/sorh_models20_design.md (GLM 5.2, Qwen 3.8 27B). One reply per prompt per cell on her 20 prompts, "
             "the same 400 texts for every model; padded is the quality judge's padding flag. Qwen 3.8 2.4T: the first "
             "sample per prompt (max_tokens 24,000). The others: max_tokens 64,000. A reply cut during reasoning, or "
             "with no record after 3 failed attempts, counts as missing.", ""]
    head_cols = ["Qwen 3.8 2.4T"] + [lab for lab, _ in cols]
    for head, cs in HEADINGS:
        lines += [f"## {head}", "", "| cell | " + " | ".join(head_cols) + " |", "|---|" + "---|" * len(head_cols)]
        lines += [f"| {c} | {kn(qwen, c)} | " + " | ".join(kn(d, c) for _, d in cols) + " |" for c in cs]
        lines.append("")
    out = Path(out) if out else ROOT / "notes" / "sorh_models20_results.md"
    out.write_text("\n".join(lines + notes))
    print(f"wrote {out}: " + ", ".join(f"{lab} {len(d)}" for lab, d in cols))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "analyse", "build_lencheck", "lencheck", "analyse_all"])
    ap.add_argument("--records", default="", help="analyse: records file (default deepseek20_64k; for tests)")
    ap.add_argument("--out", default="", help="analyse/analyse_all: output file")
    ap.add_argument("--root", default="", help="lencheck/analyse_all: the stages' folder (default logs/sorh_ablation)")
    ap.add_argument("--stage", default="", help="lencheck: the length-check stage")
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    elif a.cmd == "analyse":
        analyse(a.records, a.out)
    elif a.cmd == "build_lencheck":
        build_lencheck()
    elif a.cmd == "lencheck":
        lencheck(a.stage, a.root)
    else:
        analyse_all(a.root, a.out)
