"""Data for four extra SoRH graphs at the bottom of her page (her "show me all at the bottom of the page, dont modift
what we have", 27 Oct, on agent 1's four ideas). No new calls. The same records and judged files as
notes/sorh_hesitation_spiral_results_20.md (verified, beec613f/47696c76), without re-draws. No reasoning text is
printed or written: graphs 1-3 use the spiral judge's sentence numbers and the recorded token counts only; graph 4
uses the visible replies and the count judge's listed terms.

  .venv/bin/python src/sorh_page_graphs.py   # writes notes/sorh_page_graphs_data.json and notes/sorh_page_graphs.md

1. Score-check barcode: per reply, the reasoning as a strip of its numbered units (sorh_judges.split_units, the
   numbering the judge saw); a tick at each score check the spiral judge listed (at most 30 per reply, by its
   prompt). position = unit / units.
2. Length vs cycles: per reply, reasoning tokens as reported against the judge's score cycles.
3. Prompt x version heatmap: per prompt and version, how many of the 4 models' replies spiral, of those with a label.
4. Highlighted reply cards: sorh_160 (the sleep post, the prompt of the existing quote cards), B and G, sample 0, per
   model: the visible reply with every term the v4-sol count judge listed highlighted (whole-word, case-insensitive
   matches), and the judge's registered share.
"""
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sorh_analysis as SA  # noqa: E402
import sorh_deepseek20 as D  # noqa: E402
import sorh_judge_pass as P  # noqa: E402
import sorh_judges as J  # noqa: E402

OUT_JSON = ROOT / "notes" / "sorh_page_graphs_data.json"
OUT_MD = ROOT / "notes" / "sorh_page_graphs.md"
MODELS = P.PASSES["spiral"]
CARD_PROMPT, CARD_CELLS = "sorh_160", ("B", "G")


def replies(with_redraws=False):
    base = ROOT / "logs/sorh_ablation"
    recs = {m: P.records(m, P.ALL20) for m in MODELS}
    if with_redraws:  # her "Yes, mark as redraws": a usable re-draw replaces its cut or missing reply in the 9 cells
        import sorh_redraws as RD
        for m in (RD.QWEN, RD.DS):
            for k, r in RD.overlay(m).items():
                if k[0] in P.CELLS and k[1] in P.ALL20:
                    recs[m][k] = r
    judged = {(x["model"], x["cell"], x["prompt_id"], x.get("source_stage")): x
              for x in D.jl(base / "spiral_judge" / "judged.jsonl")}
    rows = []
    for m in MODELS:
        for c in P.CELLS:
            for p in P.ALL20:
                r = recs[m].get((c, p))
                if r is None:
                    rows.append({"model": m, "cell": c, "prompt": p, "missing": True})
                    continue
                x = judged.get((m, c, p, r.get("stage")))
                units = len(J.split_units(r.get("reasoning") or ""))
                d = (J._load(x["raw"]) or {}) if x else {}
                checks = sorted({int(v) for v in (d.get("score_checks") or [])
                                 if str(v).isdigit() and 1 <= int(v) <= units})
                ps = P.parse_spiral(x["raw"], r.get("reasoning")) if x else None
                rows.append({"model": m, "cell": c, "prompt": p, "missing": False,
                             "cut": r.get("finish") == "length" and not (r.get("reply") or "").strip(),
                             "reasoning_tokens": P.rt(r), "units": units, "score_checks": checks,
                             "positions": [round(k / units, 4) for k in checks] if units else [],
                             "cycles": ps["cycles"] if ps else None, "spirals": ps["spirals"] if ps else None,
                             "label_status": ps["status"] if ps else "not judged"})
                # counted = in k/n and the median cycles (not cut, label passes the cited-sentence rule)
                rows[-1]["counted"] = not rows[-1]["cut"] and rows[-1]["spirals"] is not None
    return rows


def heatmap(rows):
    out = {}
    for r in rows:
        if r["missing"] or r["cut"] or r["spirals"] is None:
            continue
        k = out.setdefault(f'{r["prompt"]}|{r["cell"]}', {"prompt": r["prompt"], "cell": r["cell"], "k": 0, "n": 0})
        k["n"] += 1
        k["k"] += r["spirals"] is True
    return sorted(out.values(), key=lambda v: (v["prompt"], P.CELLS.index(v["cell"])))


def spans(text, terms):
    """Character spans of the judge's terms in the reply, matched as sorh_judges.parse_count counts them (lower case,
    longest first, the same word boundaries, spaces as any whitespace), no overlaps."""
    taken, out = [], []
    for t in sorted({t.strip().lower() for t in terms if t and t.strip()}, key=lambda t: -len(t)):
        pat = re.escape(t).replace(r"\ ", r"\s+")
        for mt in re.finditer(rf"(?<![\w'-]){pat}(?![\w'-])", text, re.I):
            a, b = mt.span()
            if all(b <= x or a >= y for x, y in taken):
                taken.append((a, b))
                out.append({"start": a, "end": b, "text": text[a:b]})
    return sorted(out, key=lambda s: s["start"])


def cards():
    btext = {r["prompt_id"]: r["text"] for r in D.jl(D.OUT) if r["cell"] == "B"}[CARD_PROMPT]
    recs = {m: P.records(m, P.ALL20) for m in MODELS}
    out = []
    for m in MODELS:
        for c in CARD_CELLS:
            r = recs[m][(c, CARD_PROMPT)]
            reply = r.get("reply") or ""
            terms = (J._load((r.get("judge") or {}).get("count")) or {}).get("terms") or []
            sp = spans(reply, terms)
            meas = SA.measures(r, btext)
            out.append({"model": m, "cell": c, "prompt": CARD_PROMPT, "record": f'{c}/{CARD_PROMPT}/{r.get("sample", 0)}',
                        "stage": r.get("stage"), "reply": reply, "words": J.words(reply),
                        "judge_terms": terms, "highlight_spans": sp,
                        "highlighted_words": sum(J.words(s["text"]) for s in sp),
                        "judge_share": meas["value"], "padded_old_judge": meas["padded"]})
    return out


def main():
    rows = replies()
    hm = heatmap(rows)
    cs = cards()
    OUT_JSON.write_text(json.dumps({"source": "src/sorh_page_graphs.py", "replies": rows, "heatmap": hm, "cards": cs},
                                   ensure_ascii=False, indent=1) + "\n")
    ok = [r for r in rows if not r["missing"] and not r["cut"]]
    lines = ["# Data for four extra SoRH graphs (her 'show me all at the bottom of the page')", "",
             "Generated by `src/sorh_page_graphs.py` (measures in its docstring); the data is in "
             "`notes/sorh_page_graphs_data.json`. Same records and judged files as "
             "notes/sorh_hesitation_spiral_results_20.md, without re-draws. No reasoning text read or written.", "",
             f"Replies: {len(rows)} (4 models × 9 cells × 20 prompts); missing {sum(r['missing'] for r in rows)}; "
             f"cut during reasoning {sum(1 for r in rows if not r['missing'] and r['cut'])}; spiral label missing "
             f"{sum(1 for r in ok if r['spirals'] is None)}.", "",
             "## 1–2. Score checks and length, per model and version (replies not cut, with a label)", "",
             "| model | cell | replies | median units | median score checks | median position of 1st check | "
             "median reasoning tokens | spirals |", "|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for c in P.CELLS:
            v = [r for r in ok if r["model"] == m and r["cell"] == c and r["spirals"] is not None]
            first = [r["positions"][0] for r in v if r["positions"]]
            lines.append(f"| {m} | {c} | {len(v)} | {statistics.median([r['units'] for r in v]):.0f} | "
                         f"{statistics.median([len(r['score_checks']) for r in v]):.1f} | "
                         f"{statistics.median(first):.2f} ({len(first)} with a check) | " if first else
                         f"| {m} | {c} | {len(v)} | {statistics.median([r['units'] for r in v]):.0f} | "
                         f"{statistics.median([len(r['score_checks']) for r in v]):.1f} | — | ")
            lines[-1] += (f"{statistics.median([r['reasoning_tokens'] for r in v]):,.0f} | "
                          f"{sum(r['spirals'] for r in v)}/{len(v)} |")
    cap = sum(1 for r in ok if len(r["score_checks"]) >= 30)
    lines += ["", f"**Limit for graph 1:** the judge lists at most 30 score checks per reply; {cap} of {len(ok)} replies "
              "are at 30, so their strips may lack later checks (and their median above is capped).", "",
              "## 3. Prompt × version: models whose reply spirals (k/n of 4)", "",
              "| prompt | " + " | ".join(P.CELLS) + " |", "|---|" + "---|" * len(P.CELLS)]
    hmi = {(h["prompt"], h["cell"]): h for h in hm}
    for p in P.ALL20:
        lines.append(f"| {p} | " + " | ".join(
            f"{hmi[(p, c)]['k']}/{hmi[(p, c)]['n']}" if (p, c) in hmi else "—" for c in P.CELLS) + " |")
    lines += ["", "## 4. Highlighted reply cards (sorh_160, sample 0)", "",
              "| model | cell | words | judge share (points) | judge terms | highlighted words in the reply |",
              "|---|---|---|---|---|---|"]
    lines += [f"| {c['model']} | {c['cell']} | {c['words']} | {c['judge_share']:.1f} | {len(c['judge_terms'])} | "
              f"{c['highlighted_words']} |" for c in cs]
    lines += ["", "Highlighted words / words = the judge share on all 8 cards (the share is computed from the judge's "
              "terms the same way)."]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
