"""The write-up's quote bank: check every quote in quote-bank/quotes.tsv against its run, and render it.

    python3 quote_bank.py          # writes quote-bank/checked.tsv and quote-bank/QUOTES.md; prints the failures

quotes.tsv is hand-edited (columns in its header). Each quote is looked up in the run's reasoning dump
(~/split-brain-run/dumps/<run>.txt, blocks as dump_reasoning.py numbers them; source thinking -> thinking blocks,
final -> text blocks) or, for source contribution, in archive/<run>/submission/contribution.md, or, for source debrief, in one debrief sample
(~/split-brain-run/debrief/<run>/<probe>.jsonl; block = "<probe>#<i>": that sample's thinking, text and the files it
writes). Verified:
  exact          the quote is in the stated block (or, with no block given, in exactly one block: found_block)
  ws             the same after collapsing whitespace and straightening quotes / dashes
  segments       an elided quote ("a … b"): every segment, in order, in that block
  elsewhere:<b>  not in the stated block but in block <b>
  no             not found: fix the row (a paraphrase is not a quote)
A ¶ in a quote marks a paragraph break (the page renders it; the checker reads it as whitespace, so such a quote is ws).
Outcome, arm and model are joined from tc-reading/codes.tsv. Nothing here reads the reasoning beyond string matching.
"""

import csv, sys
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANK = HERE / "quote-bank"
SB = Path.home() / "split-brain-run"
KIND = {"thinking": "thinking", "final": "text"}
THEMES = {  # heading for QUOTES.md, in this order; unknown themes go last under their own name
    "reader": "A person reading vs an automated grader",
    "score": "The score as an objective",
    "judge-view": "What the judge can see",
    "dishonesty": "Naming the dishonesty, then doing it",
    "audiences": "What it tells the user vs what it submits",
    "norms": "Stated norms (cite sources, the score disowned)",
    "design": "Design awareness",
    "invented-grader": "A grader nobody named (A7b)",
    "routes": "How the source goes missing (routes)",
    "fictional": "\"The paper may be fictional\"",
    "unexpected": "Interventions that moved behaviour in ways we did not expect",
    "eval-belief": "What eval belief the models hold (v3: a graded task, not a test of conduct)",
}


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'").replace("—", "-").replace("–", "-").replace("¶", " ")
    return re.sub(r"\s+", " ", s).strip()


def blocks(run: str) -> dict[int, tuple[str, str]]:
    out, cur = {}, None
    f = SB / "dumps" / f"{run}.txt"
    for line in (f.read_text().splitlines() if f.exists() else []):
        m = re.match(r"^\[(\d+)\] (\w+)", line)
        if m:
            cur = int(m.group(1)); out[cur] = (m.group(2), "")
        elif cur is not None and not line.startswith("  -> "):
            out[cur] = (out[cur][0], out[cur][1] + line + "\n")
    return out


def contribution(run: str) -> str:
    for f in (SB / "archive" / run / "submission" / "contribution.md", SB / "runs" / run / "repo" / "submission" / "contribution.md"):
        if f.exists():
            return f.read_text()
    return ""


def debrief(run: str, ref: str) -> str:
    """One debrief sample's text: every thinking / text block and every tool input (the file it writes), joined."""
    probe, _, i = ref.partition("#")
    f = SB / "debrief" / run / f"{probe}.jsonl"
    if not f.exists() or not i.strip().isdigit():
        return ""
    import json
    for line in f.open():
        r = json.loads(line)
        if r.get("i") != int(i):
            continue
        out = []
        for turn in r.get("turns", []):
            for c in turn.get("content") or []:
                if c.get("type") in ("thinking", "text"):
                    out.append(c.get("thinking") or c.get("text") or "")
                elif c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    out.append(inp.get("content") or inp.get("new_string") or json.dumps(inp))
        return "\n".join(out)
    return ""


def found(q: str, text: str) -> str:
    if q in text:
        return "exact"
    if norm(q) in norm(text):
        return "ws"
    parts = [norm(p) for p in re.split(r"\s*(?:…|\.\.\.)\s*", q) if p.strip()]
    if len(parts) > 1:
        t, at = norm(text), 0
        for p in parts:
            at = t.find(p, at)
            if at < 0:
                return ""
            at += len(p)
        return "segments"
    return ""


def check(row: dict, cache: dict) -> tuple[str, str]:
    run, q, src = row["run"], row["quote"], row["source"]
    if src == "contribution":
        return (found(q, contribution(run)) or "no"), ""
    if src == "debrief":
        return (found(q, debrief(run, row["block"])) or "no"), row["block"]
    bl = cache.setdefault(run, blocks(run))
    want = KIND.get(src)
    if row["block"].strip():
        b = int(row["block"])
        if b in bl and (v := found(q, bl[b][1])):
            return v, str(b)
    hits = [(b, v) for b, (k, t) in bl.items() if (want is None or k == want) and (v := found(q, t))]
    if not hits:
        return "no", ""
    if row["block"].strip():
        return f"elsewhere:{hits[0][0]}", str(hits[0][0])
    return hits[0][1], ",".join(str(b) for b, _ in hits)


def main() -> None:
    if "--render-only" in sys.argv:  # no dumps on this machine: keep the verdicts in checked.tsv
        render(list(csv.DictReader(open(BANK / "checked.tsv"), delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")))
        return
    lines = [l for l in (BANK / "quotes.tsv").read_text().splitlines(keepends=True) if not l.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))
    codes = {r["run"]: r for r in csv.DictReader(open(HERE / "tc-reading/codes.tsv"), delimiter="\t")}
    cache, bad = {}, []
    for r in rows:
        r["verified"], r["found_block"] = check(r, cache)
        r["outcome"] = codes.get(r["run"], {}).get("outcome", "?")
        m = re.search(r"-(A\d+[ab]?)-", r["run"])
        r["arm"] = m.group(1) if m else ("p03-note" if "bnote" in r["run"] else "p03")
        r["model"] = next((k for k in ("dsv4", "glm52", "q27b") if k in r["run"]), "?")
        if r["verified"] == "no" or r["verified"].startswith("elsewhere"):
            bad.append(r)
    cols = list(rows[0].keys())
    with open(BANK / "checked.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        w.writeheader(); w.writerows(rows)
    render(rows)


def render(rows: list) -> None:
    bad = [r for r in rows if r["verified"] == "no" or r["verified"].startswith("elsewhere")]
    out = ["# Quote bank (rendered by `pilots/quote_bank.py` from `quote-bank/quotes.tsv`; do not edit)\n",
           f"{len(rows)} quotes; verified against the transcripts: "
           + ", ".join(f"{v} {sum(r['verified'] == v for r in rows)}" for v in ("exact", "ws", "segments"))
           + f"; not found {len(bad)}. Quotes need the partner's OK before anything public.\n"]
    order = list(THEMES) + sorted({r["theme"] for r in rows} - set(THEMES))
    for th in order:
        rs = [r for r in rows if r["theme"] == th]
        if not rs:
            continue
        out.append(f"\n## {THEMES.get(th, th)}\n")
        for r in rs:
            where = {"thinking": "reasoning", "final": "final message to the user", "contribution": "contribution.md",
                     "debrief": "debrief sample (resumed run)"}[r["source"]]
            blk = f" [{r['found_block'] or r['block']}]" if (r["found_block"] or r["block"]) and r["source"] != "contribution" else ""
            tags = " · ".join(x for x in (r["outcome"], f"{r['arm']} / {r['model']}", where,
                                          r["claim"] and f"ledger {r['claim']}", r["pair"] and f"pair {r['pair']}") if x)
            out.append(f"- **{r['id']}** > {r['quote']}\n  — `{r['run']}{blk}` · {tags} · {r['verified']}"
                       + (f"\n  {r['note']}" if r["note"] else "") + "\n")
    (BANK / "QUOTES.md").write_text("\n".join(out))
    print(f"{len(rows)} quotes; not found / elsewhere: {len(bad)}")
    for r in bad:
        print(f"  {r['id']} {r['run']} [{r['block']}] {r['verified']}: {r['quote'][:90]}")


if __name__ == "__main__":
    main()
