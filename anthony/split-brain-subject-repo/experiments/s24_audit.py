"""Independent pre-read audit of S24's val2 split (steward's card for A; studies/S24.md is C's). No readouts are read.

  python experiments/s24_audit.py [--families typo,association,multihop]

Checks, per family: (1) no target / accepted form and no prompt shared with bench, fit or val, exactly or normalised
(case, punctuation, articles, a trailing plural s), and no near-duplicate prompt (token Jaccard >= 0.8); (2) the format
matches val (item keys, the bench's render and read plan via ``jlm.banks.specs``, prompt token lengths); (3) the
subfamily mix next to val's (``--jsonl`` audits filtered items before they are frozen, and items marked ``fresh_target``
are checked separately, since jle's rule lets closed-answer items repeat a bank's answer); (4) whether the authoring / gate code touches a centre, a lens readout or out/eval
(a grep of experiments/s24_build.py). Writes ``out/analysis/S24-audit/audit.md``.
"""

import argparse
import json
import re
import statistics
from collections import Counter

from jlm import OUT, REPO_ROOT, banks

ARTICLES = re.compile(r"^(the|a|an)\s+")


def norm(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s.casefold()).strip()
    s = ARTICLES.sub("", re.sub(r"\s+", " ", s))
    return s[:-1] if len(s) > 3 and s.endswith("s") and not s.endswith("ss") else s


def targets(it: dict) -> set[str]:
    ws = [it.get("target"), it.get("typo"), *it.get("target_alts", []), *it.get("intermediates", []), *banks.targets(it)]
    return {w for w in ws if isinstance(w, str) and w.strip()}


def prompt(it: dict) -> str:
    return it.get("prompt") or " ".join(m.get("content", "") for m in it.get("messages", []))


def toks(s: str) -> set[str]:
    return set(re.findall(r"\w+", s.casefold()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--families", default="typo,association,multihop")
    ap.add_argument("--split", default="val2", help="the held-out split's name (val2), or a label for --jsonl")
    ap.add_argument("--also", default="", help="held-out splits to compare against too, e.g. val2,val2b (where they exist)")
    ap.add_argument("--jsonl", default="", help="audit filtered items in <dir>/<family>.jsonl before they are frozen")
    args = ap.parse_args()
    from transformers import AutoTokenizer
    from umot.provenance import PINS

    from jlm.lens import MODEL

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    lines = ["# S24 val2: independent pre-read audit (A; no readouts read)", ""]
    for f in args.families.split(","):
        if args.jsonl:
            from pathlib import Path

            from jlm.banks import Bank

            src = Path(args.jsonl) / f"{f}.jsonl"
            vb = banks.load(f, "val")
            raw = [json.loads(line) for line in src.open() if line.strip()]
            v2 = Bank(f, args.split, src, vb.header, [{**it, "id": it.get("id", it.get("name"))} for it in raw])
        else:
            v2 = banks.load(f, args.split)
        others = {s: banks.load(f, s) for s in ("bench", "fit", "val")}
        for s in filter(None, args.also.split(",")):
            try:
                others[s] = banks.load(f, s)
            except (FileNotFoundError, ValueError):
                pass
        lines += [f"## {f}: {len(v2.items)} items", ""]
        # (1) overlap
        for s, b in others.items():
            T = {t.casefold() for it in b.items for t in targets(it)}
            Tn = {norm(t) for it in b.items for t in targets(it)}
            P = {prompt(it).casefold().strip() for it in b.items}
            Pn = {norm(prompt(it)) for it in b.items}
            PT = [toks(prompt(it)) for it in b.items]
            tx = [(it["name"] if "name" in it else it.get("id"), t) for it in v2.items for t in targets(it) if t.casefold() in T]
            tn = [(it["name"] if "name" in it else it.get("id"), t) for it in v2.items for t in targets(it) if norm(t) in Tn and t.casefold() not in T]
            px = [it.get("name") for it in v2.items if prompt(it).casefold().strip() in P]
            pn = [it.get("name") for it in v2.items if norm(prompt(it)) in Pn]
            near = []
            for it in v2.items:
                a = toks(prompt(it))
                best = max((len(a & b2) / len(a | b2) for b2 in PT if a | b2), default=0.0)
                if best >= 0.8:
                    near.append((it.get("name"), round(best, 2)))
            fresh = {it.get("name") for it in v2.items if it.get("fresh_target", True)}
            txf = [x for x in tx + tn if x[0] in fresh]
            if any("fresh_target" in it for it in v2.items):
                lines.append(f"- vs {s}: shared targets on items marked fresh_target: {len(txf)} {txf[:6]}; by subfamily of all "
                             f"shared: {dict(Counter(next(i.get('subfamily') for i in v2.items if i.get('name') == n) for n, _ in tx + tn))}")
            lines.append(f"- vs {s}: targets exact {len(tx)} {tx[:6]}, normalised-only {len(tn)} {tn[:6]}; prompts exact "
                         f"{len(px)}, normalised {len(pn)}, near-duplicate (Jaccard >= 0.8) {len(near)} {near[:4]}")
        # (2) format
        kv = Counter(k for it in others["val"].items for k in it)
        k2 = Counter(k for it in v2.items for k in it)
        missing = sorted(k for k in kv if kv[k] == len(others["val"].items) and k2[k] < len(v2.items))
        sp_v, sp_2 = banks.specs(others["val"]), banks.specs(v2)
        rv = Counter((s.render, json.dumps(s.positions, sort_keys=True)) for s in sp_v)
        r2 = Counter((s.render, json.dumps(s.positions, sort_keys=True)) for s in sp_2)
        lv = [len(tok(prompt(it), add_special_tokens=False)["input_ids"]) for it in others["val"].items]
        l2 = [len(tok(prompt(it), add_special_tokens=False)["input_ids"]) for it in v2.items]
        q = lambda xs: (min(xs), statistics.median(xs), max(xs))  # noqa: E731
        lines.append(f"- format: keys every val item has but some val2 items lack: {missing or 'none'}; render / read plan "
                     f"val {dict(rv)} vs val2 {dict(r2)}; prompt tokens (min / median / max) val {q(lv)} vs val2 {q(l2)}")
        ttv = Counter(len(tok(" " + it.get("target", ""), add_special_tokens=False)["input_ids"]) for it in others["val"].items if it.get("target"))
        tt2 = Counter(len(tok(" " + it.get("target", ""), add_special_tokens=False)["input_ids"]) for it in v2.items if it.get("target"))
        lines.append(f"- target length in tokens (with a leading space): val {dict(sorted(ttv.items()))} vs val2 {dict(sorted(tt2.items()))}")
        # (3) mix
        lines.append(f"- subfamily mix: val {dict(Counter(it.get('subfamily') for it in others['val'].items))} vs val2 "
                     f"{dict(Counter(it.get('subfamily') for it in v2.items))}")
        lines.append("")
    # (4) selection on a centre
    src = (REPO_ROOT / "experiments" / "s24_build.py").read_text()
    hits = sorted(set(re.findall(r"\b(centres?|evaluate|readouts?|out/eval|Lens\b|jlm\.lens|J_l|fam@|knnx|s14)\w*", src)))
    lines += ["## Authoring code", "", f"- experiments/s24_build.py mentions: {hits or 'none of centre / readout / lens / out/eval'}", ""]
    out = OUT / "analysis" / "S24-audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"audit-{args.split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
