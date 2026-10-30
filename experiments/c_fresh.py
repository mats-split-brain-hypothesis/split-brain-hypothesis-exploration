"""Night-2 finalists on fresh vs shared answers (val strict, the five single-token families; steward's card).

An item's answers are "fresh (other)" when none of its accepted ids occurs among the accepted ids of the OTHER families'
fit items, "fresh (any)" when none occurs in ANY fit bank (own family included). A centre fitted with other families'
targets (S20x, S21) can only be helped by recurring answers on the shared items; a target-free centre shows how much
of a split is target frequency rather than leakage. Strict scorer (evaluate.scorers), readouts from out/eval.
Writes out/analysis/fresh/finalists.md.

  python experiments/c_fresh.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import read_jsonl, scorers
from transformers import AutoTokenizer
from umot.provenance import PINS
from wsbench.produce.render import display_tokens

from jlm import OUT, banks, capture, score
from jlm.capture import MODEL

FAMS = ["typo", "association", "basic_readout", "multihop", "multilingual"]
ALL = FAMS + ["user_modeling", "directed_modulation"]
ARMS = {
    "cos": {"fam": "fam-at-fit__cos", "s14t64": "s14t64-at-fit__cos", "S14k": "sched~40~kmx64+s14t64-at-fit__cos",
            "S14b": "sched~40~kmx64+s14~template~64~mean=kmx64~a=0.5-at-fit__cos", "knnxs8": "knnxs8-at-fit__cos",
            "S20x": "s20xt~1-at-fit__cos", "S21": "sched~40~s20xon~1~kmx64+s14t64-at-fit__cos"},
    "rms": {"fam": "fam-at-fit__rms", "s14t64": "s14t64-at-fit__rms", "S14k": "sched~40~kmx64+s14t64-at-fit__rms",
            "S14b": "sched~40~kmx64+s14~template~64~mean=kmx64~a=0.5-at-fit__rms", "knnxs8": "knnxs8-at-fit__rms",
            "S20x": "s20xtrms~1-at-fit__rms", "S21": "sched~40~s20xonrms~1~kmx64+s14t64-at-fit__rms"},
}


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    vocab = display_tokens(tok, list(range(len(tok))))

    def accepted(f: str, s: str):
        b = banks.load(f, s)
        st, _ = scorers(b, vocab, {it.id: display_tokens(tok, it.ids) for it in capture.load(b)})
        return b, {i: set(x) for i, x in st.accepted.items() if not st.conf[i] and x}

    fit = {f: set().union(*accepted(f, "fit")[1].values()) for f in ALL}
    md = ["# Night-2 finalists on fresh vs shared answers (val strict, 5 single-token families)", "",
          "fresh (other) = no accepted id among the other families' fit targets; fresh (any) = none in any fit bank.", ""]
    for ro, arms in ARMS.items():
        acc = {a: {"all": [0, 0], "fresh_o": [0, 0], "shared_o": [0, 0], "fresh_a": [0, 0]} for a in arms}
        per = []
        for f in FAMS:
            b, va = accepted(f, "val")
            other = set().union(*(fit[g] for g in ALL if g != f))
            anyf = other | fit[f]
            P = {a: score.strict_items(read_jsonl(OUT / "eval" / f / "val" / s / "readouts.jsonl"), b) for a, s in arms.items()}
            ids = [i for i in va if all(i in P[a] for a in arms)]
            groups = {"all": ids, "fresh_o": [i for i in ids if not va[i] & other],
                      "shared_o": [i for i in ids if va[i] & other], "fresh_a": [i for i in ids if not va[i] & anyf]}
            per.append(f"| {f} ({ro}) | {len(ids)} | {len(groups['fresh_o'])} | {len(groups['fresh_a'])} | "
                       + " | ".join(f"{sum(P[a][i] for i in groups['fresh_o']) / max(1, len(groups['fresh_o'])):.3f}" for a in arms) + " |")
            for a in arms:
                for g, L in groups.items():
                    acc[a][g][0] += sum(P[a][i] for i in L)
                    acc[a][g][1] += len(L)
        md += [f"## {ro}", "", "| arm | all | fresh (other) | shared (other) | fresh (any) | Δ fam all | Δ fam fresh (other) | Δ fam fresh (any) |",
               "|---|---|---|---|---|---|---|---|"]
        r = {a: {g: v[0] / max(1, v[1]) for g, v in acc[a].items()} for a in arms}
        n = {g: acc["fam"][g][1] for g in acc["fam"]}
        for a in arms:
            md.append(f"| {a} | {r[a]['all']:.3f} | {r[a]['fresh_o']:.3f} | {r[a]['shared_o']:.3f} | {r[a]['fresh_a']:.3f} | "
                      f"{r[a]['all'] - r['fam']['all']:+.3f} | {r[a]['fresh_o'] - r['fam']['fresh_o']:+.3f} | {r[a]['fresh_a'] - r['fam']['fresh_a']:+.3f} |")
        md += [f"(items pooled: all {n['all']}, fresh (other) {n['fresh_o']}, shared (other) {n['shared_o']}, fresh (any) {n['fresh_a']})", "",
               "Per family, fresh (other) only:", "", "| family | n | fresh (other) | fresh (any) | " + " | ".join(arms) + " |",
               "|---|---|---|---|" + "---|" * len(arms)] + per + [""]
    out = OUT / "analysis" / "fresh"
    out.mkdir(parents=True, exist_ok=True)
    (out / "finalists.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
