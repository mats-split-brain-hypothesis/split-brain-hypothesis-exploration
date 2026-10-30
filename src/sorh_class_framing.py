"""Why the class framing ("this is for a class I'm taking" ... "our teacher marks it by ...", r_student) pads less
than the plain score sentence (G), on all four models, paired by prompt (her "I need investigation and examples of
why the class framing leads to less padding, to add to the first observation", via the orchestrator, 27 Oct).
Existing data only: no calls, no reasoning read (judge labels and recorded token counts only; notes hand-coded from
the visible replies).

  .venv/bin/python src/sorh_class_framing.py dump    # print every note to the person (visible text), for coding
  .venv/bin/python src/sorh_class_framing.py         # writes notes/sorh_class_framing.md

Records: the page tables' (sorh_padding_final.table_set), G and r_student, sample 0 (Qwen 3.8 2.4T: its first sample).
Padded = the page's main label (padding v2: the unchanged judge on the final output, no-output fix applied).

Measures:
1. Flips: same model and prompt, the padded label differs. Metric type of each prompt: share (SHARE_ROWS), term count
   (TERMS_ROWS outside SHARE_ROWS) or item count (the rest).
2. Final-output measure: the registered count judge's output, kept to the final output (what the padding judge saw):
   - term prompts: sorh_judges.parse_count on the final output's text (share prompts: its share, in points);
   - item prompts: the judge's items whose cited sentence (sorh_judges.split_units of the whole reply) starts inside
     the final output.
   Density = count per 100 final-output words (share prompts: the share in points). Whole-reply counts recomputed the
   same way are asserted equal to the registered ones.
3. Notes = the text the final-output cut removed around the deliverable (a note: more than 40 characters). Coding
   scheme, fixed before the notes were coded (several codes per note allowed):
   - T: mentions the teacher, the class, a grade or mark, or the assignment;
   - S: states or discusses the scored count itself (e.g. "I included 30 questions", a phrase count);
   - Q: weighs quality against the score (e.g. keeping it natural while hitting the count);
   - A: offers to change the amount, or tells the person they can use fewer or more (e.g. "pick the 10-15 that matter");
   - H: none of these (introduces or signs off, offers more help).
   Codes are in notes/sorh_class_notes_codes.json (agent 1, hand-coded on the visible text).
4. Judge labels and length, G vs class: the Sol reasoning judge's fields (Qwen 3.8 2.4T: its in-stage labels; the
   others: the hesitation pass), the spiral label, reasoning tokens (as reported).
5. Examples, fixed rule: per model, the pairs with G padded and class not padded where both replies finished "stop",
   the first three by prompt id. Shown: the final output's opening 500 characters with the counted items in bold.
"""
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sorh_deepseek20 as D  # noqa: E402
import sorh_judge_pass as P  # noqa: E402
import sorh_judges as J  # noqa: E402
import sorh_padding_final as PF  # noqa: E402

OUT = ROOT / "notes" / "sorh_class_framing.md"
CODES = ROOT / "notes" / "sorh_class_notes_codes.json"
MODELS = ["Qwen 3.8 2.4T", "DeepSeek V4 Pro", "GLM 5.2", "Qwen 3.8 27B"]
LAB = {"qwen/qwen3.8-2.4t-a95b": "Qwen 3.8 2.4T", "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro",
       "z-ai/glm-5.2": "GLM 5.2", "qwen/qwen3.8-27b": "Qwen 3.8 27B"}
CELLS = ("G", "r_student")
NOTE = 40
OPEN = 500


def mtype(row):
    return "share" if row in J.SHARE_ROWS else "term count" if row in J.TERMS_ROWS else "item count"


def unit_offsets(reply):
    offs, cur = [], 0
    for u in J.split_units(reply):
        i = reply.find(u, cur)
        offs.append(i)
        if i >= 0:
            cur = i + len(u)
    return offs


def items_kept(raw, reply):
    """The count judge's items as parse_count keeps them: (sentence number, item)."""
    d = J._load(raw) or {}
    entries = [x for x in (d.get("items") or []) if isinstance(x, dict)]
    n = len(J.split_units(reply))
    kept = [x for x in entries if isinstance(x.get("sentence"), int) and not isinstance(x.get("sentence"), bool)
            and 1 <= x["sentence"] <= n]
    return list({(x["sentence"], J._norm(str(x.get("item", "")))): x for x in kept}.values())


def measure(r, final, fs):
    """(count in the final output, density per 100 final words or share points, whole-reply count) or Nones."""
    raw, row, reply = (r.get("judge") or {}).get("count"), r["row"], r.get("reply") or ""
    whole = J.parse_count(raw, row, reply)
    if whole["count"] is None:
        return None, None, None
    w = J.words(final)
    if row in J.TERMS_ROWS:
        c = J.parse_count(raw, row, final)
        if row in J.SHARE_ROWS:
            return c["count"], (100 * c["share"] if c["share"] is not None else None), whole["count"]
        return c["count"], (100 * c["count"] / w if w else None), whole["count"]
    kept = items_kept(raw, reply)
    assert len(kept) == whole["count"], (r["cell"], r["prompt_id"])
    offs = unit_offsets(reply)
    fe = fs + len(final)
    inside = [x for x in kept if offs[x["sentence"] - 1] >= 0 and fs <= offs[x["sentence"] - 1] < fe]
    return len(inside), (100 * len(inside) / w if w else None), whole["count"]


def pairs():
    base = ROOT / "logs/sorh_ablation"
    lab = {x["key"]: x for x in D.jl(base / PF.OUTDIR / PF.V2_OUT)}
    for x in D.jl(base / PF.OUTDIR / PF.FIX_OUT):
        lab[x["key"]] = dict(lab[x["key"]], padding_final_nometric=x["padding_final_nometric"], why=x.get("why"),
                             fixed_whole=True)
    out = {}
    for st, i, r in PF.table_set(base):
        if r["cell"] not in CELLS:
            continue
        reply = r.get("reply") or ""
        if r.get("finish") == "length" and not reply.strip():
            continue
        x = lab[PF.key(st, i, r)]
        if x.get("fixed_whole") or x["has_output"] is False or x.get("cut_failed"):
            final = reply
        else:
            raw = (x.get("cut_raws") or [None])[-1]
            final = (PF.parse_cut(raw, reply)[1] if raw else None) or reply
        fs = reply.find(final) if final else 0
        assert fs >= 0 and len(reply) - len(final) == (x.get("chars_removed") or 0) or x.get("fixed_whole")
        cnt, dens, whole = measure(r, final, fs)
        out[(LAB[r["model"]], r["prompt_id"], r["cell"])] = {
            "rec": r, "padded": x["padding_final_nometric"], "old": x["old_padded"], "why": x.get("why"),
            "reply": reply, "final": final, "fs": fs, "before": reply[:fs].strip(),
            "after": reply[fs + len(final):].strip(), "removed": len(reply) - len(final),
            "words": J.words(final), "count": cnt, "density": dens, "whole": whole, "row": r["row"],
            "finish": r.get("finish"), "stage": st}
    return out


def note_text(x):
    return " […] ".join(t for t in (x["before"], x["after"]) if t)


def dump():
    data = pairs()
    for (m, p, c), x in sorted(data.items()):
        if x["removed"] > NOTE:
            print(f"\n=== {m} | {p} | {c} | {x['removed']} chars")
            print(note_text(x))


def med(v):
    return statistics.median(v) if v else None


def fmt(v, d=1):
    return "—" if v is None else f"{v:.{d}f}"


def hes_labels():
    base = ROOT / "logs/sorh_ablation"
    judged = {(x["model"], x["cell"], x["prompt_id"], x.get("source_stage")): x
              for x in D.jl(base / "hesitation_judge" / "judged.jsonl")}
    out = {}
    for m in MODELS:
        for (c, p), r in P.records(m, P.ALL20).items():
            if c not in CELLS or (r.get("finish") == "length" and not (r.get("reply") or "").strip()):
                continue
            raw = (r.get("judge") or {}).get("reasoning") if m == "Qwen 3.8 2.4T" else \
                (judged.get((m, c, p, r.get("stage"))) or {}).get("raw")
            out[(m, p, c)] = J.parse_reasoning(raw, r.get("reasoning") or "") if raw else None
    return out


def excerpt(text, spans, n=OPEN):
    """The opening of text up to the last space before n characters, with the reply's own ** removed and every
    counted span that ends inside it in bold."""
    cut = n if len(text) <= n else (text.rfind(" ", 0, n) if text.rfind(" ", 0, n) > n // 2 else n)
    skip = set()
    for mt in re.finditer(r"\*\*", text[:cut]):
        skip.update((mt.start(), mt.start() + 1))
    starts = {a for a, b in spans if b <= cut}
    ends = {b for a, b in spans if b <= cut}
    out = []
    for i, ch in enumerate(text[:cut] + " "):
        if i in ends:
            out.append("**")
        if i in starts:
            out.append("**")
        if i < cut and i not in skip:
            out.append(ch)
    s = "".join(out).rstrip()
    return s + (" …" if cut < len(text) else "")


def counted_spans(x):
    """Character spans, in the final output, of what the count judge counted."""
    r, final = x["rec"], x["final"]
    raw = (r.get("judge") or {}).get("count")
    if x["row"] in J.TERMS_ROWS:
        terms = (J._load(raw) or {}).get("terms") or []
        spans, taken = [], []
        for t in sorted({t.strip().lower() for t in terms if isinstance(t, str) and t.strip()}, key=lambda t: -len(t)):
            pat = re.escape(t).replace(r"\ ", r"\s+")
            for mt in re.finditer(rf"(?<![\w'-]){pat}(?![\w'-])", final, re.I):
                if all(mt.end() <= a or mt.start() >= b for a, b in taken):
                    taken.append(mt.span())
        return taken
    offs, units = unit_offsets(x["reply"]), J.split_units(x["reply"])
    out = []
    for it in items_kept(raw, x["reply"]):
        o = offs[it["sentence"] - 1]
        if o >= x["fs"] and o < x["fs"] + len(final):
            out.append((o - x["fs"], o - x["fs"] + len(units[it["sentence"] - 1])))
    return sorted(set(out))


def main():
    data = pairs()
    codes = json.loads(CODES.read_text()) if CODES.exists() else {}
    prompts = sorted({p for _, p, _ in data})
    both = {m: [p for p in prompts if (m, p, "G") in data and (m, p, "r_student") in data] for m in MODELS}
    fwd = {m: [p for p in both[m] if data[(m, p, "G")]["padded"] and data[(m, p, "r_student")]["padded"] is False]
           for m in MODELS}
    rev = {m: [p for p in both[m] if data[(m, p, "G")]["padded"] is False and data[(m, p, "r_student")]["padded"]]
           for m in MODELS}
    L = ["# Why the class framing pads less: G vs class, four models, paired by prompt", "",
         "Generated by `src/sorh_class_framing.py` (measures and the fixed rules in its docstring). Existing data only: "
         "no calls, no reasoning read. G = the request + its score sentence; class = 'this is for a class I'm "
         "taking.' + the request, with 'our teacher marks it by …' in place of 'Your … will be scored by …'.", ""]
    # 1. flips
    L += ["## 1. Which prompts flip", "",
          "| model | G padded | class padded | padded → not (class) | not → padded (class) |", "|---|---|---|---|---|"]
    for m in MODELS:
        L.append(f"| {m} | {sum(data[(m, p, 'G')]['padded'] is True for p in both[m])}/{len(both[m])} | "
                 f"{sum(data[(m, p, 'r_student')]['padded'] is True for p in both[m])}/{len(both[m])} | "
                 f"{len(fwd[m])}: {', '.join(fwd[m]) or '—'} | {len(rev[m])}: {', '.join(rev[m]) or '—'} |")
    byp = Counter(p for m in MODELS for p in fwd[m])
    byr = Counter(p for m in MODELS for p in rev[m])
    L += ["", "Prompts that flip padded → not on more than one model: " + ", ".join(
        f"{p} ({k} models)" for p, k in byp.most_common() if k > 1) + "; the reverse on more than one model: " +
        (", ".join(f"{p} ({k})" for p, k in byr.most_common() if k > 1) or "none") + ".", ""]
    L += ["| metric type | prompts | pairs | G padded | class padded | padded → not | not → padded |",
          "|---|---|---|---|---|---|---|"]
    for t in ("item count", "term count", "share"):
        ps = [p for p in prompts if mtype(int(p.split("_")[1])) == t]
        pr = [(m, p) for m in MODELS for p in both[m] if p in ps]
        L.append(f"| {t} | {len(ps)} | {len(pr)} | {sum(data[(m, p, 'G')]['padded'] is True for m, p in pr)} | "
                 f"{sum(data[(m, p, 'r_student')]['padded'] is True for m, p in pr)} | "
                 f"{sum(p in fwd[m] for m, p in pr)} | {sum(p in rev[m] for m, p in pr)} |")
    # 2. final-output measure
    L += ["", "## 2. How stuffed is the final output itself", "",
          "Density = scored items per 100 words of the final output (share prompts: the share in points). Paired by "
          "prompt; ratio = (class + 1) / (G + 1).", "",
          "| model | pairs with a measure | class density lower | higher | equal | median ratio | class count lower | "
          "median words G → class |", "|---|---|---|---|---|---|---|---|"]
    def dpairs(m, ps):
        return [(data[(m, p, "G")], data[(m, p, "r_student")]) for p in ps
                if data[(m, p, "G")]["density"] is not None and data[(m, p, "r_student")]["density"] is not None]
    for m in MODELS:
        v = dpairs(m, both[m])
        lo = sum(b["density"] < a["density"] - 1e-9 for a, b in v)
        hi = sum(b["density"] > a["density"] + 1e-9 for a, b in v)
        L.append(f"| {m} | {len(v)} | {lo} | {hi} | {len(v) - lo - hi} | "
                 f"{med([(b['density'] + 1) / (a['density'] + 1) for a, b in v]):.2f} | "
                 f"{sum(b['count'] < a['count'] for a, b in v)} | {med([a['words'] for a, _ in v]):.0f} → "
                 f"{med([b['words'] for _, b in v]):.0f} |")
    L += ["", "By what happens to the label (all four models together):", "",
          "| pairs | n | class density lower | median density ratio | median count ratio |", "|---|---|---|---|---|"]
    groups = {"G padded → class not": [(m, p) for m in MODELS for p in fwd[m]],
              "both padded": [(m, p) for m in MODELS for p in both[m]
                              if data[(m, p, "G")]["padded"] and data[(m, p, "r_student")]["padded"]],
              "both not padded": [(m, p) for m in MODELS for p in both[m]
                                  if data[(m, p, "G")]["padded"] is False and data[(m, p, "r_student")]["padded"] is False],
              "G not → class padded": [(m, p) for m in MODELS for p in rev[m]]}
    for g, mp in groups.items():
        v = [(data[(m, p, "G")], data[(m, p, "r_student")]) for m, p in mp
             if data[(m, p, "G")]["density"] is not None and data[(m, p, "r_student")]["density"] is not None]
        L.append(f"| {g} | {len(v)} | {sum(b['density'] < a['density'] - 1e-9 for a, b in v)} | "
                 f"{fmt(med([(b['density'] + 1) / (a['density'] + 1) for a, b in v]), 2)} | "
                 f"{fmt(med([(b['count'] + 1) / (a['count'] + 1) for a, b in v]), 2)} |")
    L += ["", "By metric type (all four models together):", "",
          "| metric type | pairs with a measure | class count lower | median count ratio | class density lower | "
          "median density ratio | median words G → class |", "|---|---|---|---|---|---|---|"]
    for t in ("item count", "term count", "share"):
        v = [(data[(m, p, "G")], data[(m, p, "r_student")]) for m in MODELS for p in both[m]
             if mtype(data[(m, p, "G")]["row"]) == t and data[(m, p, "G")]["density"] is not None
             and data[(m, p, "r_student")]["density"] is not None]
        L.append(f"| {t} | {len(v)} | {sum(b['count'] < a['count'] for a, b in v)} | "
                 f"{fmt(med([(b['count'] + 1) / (a['count'] + 1) for a, b in v]), 2)} | "
                 f"{sum(b['density'] < a['density'] - 1e-9 for a, b in v)} | "
                 f"{fmt(med([(b['density'] + 1) / (a['density'] + 1) for a, b in v]), 2)} | "
                 f"{med([a['words'] for a, _ in v]):.0f} → {med([b['words'] for _, b in v]):.0f} |")
    # 3. notes
    L += ["", "## 3. Notes to the person around the deliverable", "",
          f"A note = more than {NOTE} characters cut around the final output; 'any cut' counts every cut (Qwen 3.8 "
          "27B's 2-character cuts are leftover whitespace).", "",
          "| model | version | any cut | with a note | median note length (chars) | T teacher/grade | S the count | "
          "Q quality vs score | A fewer/more | H none of these |", "|---|---|---|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for c in CELLS:
            xs = [(p, data[(m, p, c)]) for p in both[m]]
            nts = [(p, x) for p, x in xs if x["removed"] > NOTE]
            cc = Counter(k for p, _ in nts for k in codes.get(f"{m}|{p}|{c}", []))
            coded = sum(f"{m}|{p}|{c}" in codes for p, _ in nts)
            L.append(f"| {m} | {'G' if c == 'G' else 'class'} | {sum(x['removed'] > 0 for _, x in xs)}/{len(xs)} | "
                     f"{len(nts)}/{len(xs)} | {fmt(med([x['removed'] for _, x in nts]), 0)} | " +
                     " | ".join(f"{cc[k]}" for k in "TSQAH") + (f" |" if coded == len(nts) else f" (coded {coded}) |"))
    # 4. judge labels
    hl = hes_labels()
    sp = {(r["model"], r["prompt"], r["cell"]): r for r in __import__("sorh_page_graphs").replies()}
    L += ["", "## 4. Reasoning-judge labels and length, G vs class", "",
          "k/n over replies with a label (cut replies left out). Spirals: the replies counted in the verified k/n. "
          "Reasoning tokens as reported.", "",
          "| label | " + " | ".join(f"{m} G | {m} class" for m in MODELS) + " |", "|---|" + "---|---|" * len(MODELS)]
    for f in J.REASONING_FIELDS:
        row = []
        for m in MODELS:
            for c in CELLS:
                v = [hl[(m, p, c)][f] for p in prompts if hl.get((m, p, c)) and hl[(m, p, c)][f] is not None]
                row.append(f"{sum(v)}/{len(v)}")
        L.append(f"| {f} | " + " | ".join(row) + " |")
    row = []
    for m in MODELS:
        for c in CELLS:
            v = [sp[(m, p, c)]["spirals"] for p in prompts if (m, p, c) in sp and sp[(m, p, c)]["counted"]]
            row.append(f"{sum(v)}/{len(v)}")
    L.append("| spirals | " + " | ".join(row) + " |")
    row = []
    for m in MODELS:
        for c in CELLS:
            v = [sp[(m, p, c)]["reasoning_tokens"] for p in prompts if (m, p, c) in sp and not sp[(m, p, c)]["missing"]]
            row.append(f"{med(v):,.0f}")
    L.append("| median reasoning tokens | " + " | ".join(row) + " |")
    L += ["", "Paired by prompt: " + "; ".join(
        f"{m}: class reasoning shorter on {sum(sp[(m, p, 'r_student')]['reasoning_tokens'] < sp[(m, p, 'G')]['reasoning_tokens'] for p in prompts if (m, p, 'G') in sp and (m, p, 'r_student') in sp)}/20"
        for m in MODELS) + ".", ""]
    sp_f = [(sp.get((m, p, "G")) or {}, sp.get((m, p, "r_student")) or {}) for m in MODELS for p in fwd[m]]
    L += [f"In the {len(sp_f)} padded → not flips: G spirals {sum(a.get('spirals') is True for a, _ in sp_f)}, class "
          f"spirals {sum(b.get('spirals') is True for _, b in sp_f)} (of those with a label: "
          f"{sum(a.get('counted', False) for a, _ in sp_f)} G, {sum(b.get('counted', False) for _, b in sp_f)} class).", ""]
    # 5. examples
    L += ["## 5. Examples (fixed rule: per model, the first three padded → not flips by prompt id where both replies "
          "finished 'stop')", ""]
    for m in MODELS:
        ex = [p for p in fwd[m] if data[(m, p, "G")]["finish"] == "stop" and data[(m, p, "r_student")]["finish"] == "stop"][:3]
        for p in ex:
            L += [f"### {m}, {p} ({mtype(data[(m, p, 'G')]['row'])})", ""]
            for c in CELLS:
                x = data[(m, p, c)]
                cnt = (f"{x['count']} counted ({fmt(x['density'])} per 100 words)" if x["count"] is not None else
                       "count judge's output unparsed")
                L += [f"**{'G' if c == 'G' else 'Class'}:** padded {x['padded']}; final output {x['words']} words, "
                      f"{cnt}; note around it: {x['removed']} characters. Judge: {x['why']}", ""]
                L += ["> " + excerpt(x["final"], counted_spans(x)).strip().replace("\n", "\n> "), ""]
                if x["removed"] > NOTE:  # line breaks shown as " / " so the note's own markdown can't break the page
                    L += ["Note: “" + re.sub(r"\s*\n\s*", " / ", note_text(x)).replace("**", "") + "”", ""]
    OUT.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    dump() if sys.argv[1:] == ["dump"] else main()
