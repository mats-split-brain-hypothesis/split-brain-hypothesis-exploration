"""Per-unit reporting (S10) of the night's round-2 survivors on the _mt families, val: the piece proxy per unit
(``study_S4_units``'s rule, via the readouts) and, where a judged run exists, the Haiku item pass and per-unit hit rates.
Offline (readouts and judged results only). Writes out/analysis/mt-units-round2/table.md.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from transformers import AutoTokenizer  # noqa: E402
from umot.provenance import PINS  # noqa: E402
from wsbench.produce.render import display_tokens  # noqa: E402

from jlm import OUT, banks, mtproxy  # noqa: E402
from jlm.lens import MODEL  # noqa: E402

FAMS = ["typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
ARMS = [("zero", "zero|cos"), ("fam", "fam@fit|cos"), ("s14t64 (A)", "s14t64@fit|cos"),
        ("S14k (A)", "sched:40:kmx64+s14t64@fit|cos"), ("S14b (A)", "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5@fit|cos"),
        ("S20x (B, sup.)", "s20xt:1@fit|cos"), ("S21 (B, sup.)", "sched:40:s20xon:1:kmx64+s14t64@fit|cos"),
        ("knnxs8 (B)", "knnxs8@fit|cos"), ("knnx8", "knnx8@fit|cos")]


def slug(a: str) -> str:
    return a.replace("|", "__").replace("@", "-at-").replace(":", "~")


def main() -> None:
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    disp = lambda ids: display_tokens(tok, ids)  # noqa: E731
    lines = ["# Round-2 survivors on the _mt families, per unit (val)", "",
             "Piece proxy per unit (share of reachable items whose unit has a distinctive piece in some cell's top 10 at any",
             "layer) and the proxy's item pass (all required units at one layer); Haiku (unpinned dev judge) item pass and",
             "per-unit hit share where a judged run exists ('-' otherwise). sup. = supervised (other families' fit targets).", ""]
    for f in FAMS:
        bank = banks.load(f, "val")
        units = mtproxy.units_of(bank, tok, disp)
        ids = [i for i, ok in mtproxy.reachable(units).items() if ok]
        roles = sorted({u.role for i in ids for u in units[i]})
        req = sorted({u.role for i in ids for u in units[i] if u.required})
        lines += [f"## {f} ({len(ids)} reachable items; required: {', '.join(req)})", "",
                  "| arm | " + " | ".join(f"proxy {r}" for r in roles) + " | proxy pass | Haiku pass | "
                  + " | ".join(f"Haiku {r}" for r in req) + " |",
                  "|---|" + "---|" * (len(roles) + 2 + len(req))]
        for label, arm in ARMS:
            p = OUT / "eval" / f / "val" / slug(arm) / "readouts.jsonl"
            if not p.exists():
                lines.append(f"| {label} | " + " | ".join("-" for _ in range(len(roles) + 2 + len(req))) + " |")
                continue
            rows = [json.loads(x) for x in p.read_text().splitlines()]
            hit = defaultdict(set)
            for r in rows:
                t = set(r["tokens"])
                for u in units.get(r["id"], []):
                    if t & u.pieces:
                        hit[r["id"]].add(u.role)
            share = {ro: sum(ro in hit[i] for i in ids if any(u.role == ro for u in units[i]))
                     / max(1, sum(any(u.role == ro for u in units[i]) for i in ids)) for ro in roles}
            ps = mtproxy.item_passes(rows, units)
            proxy = sum(ps[i] for i in ids) / len(ids)
            j = p.parent / "judged-claude-haiku-5.5" / "results.json"
            if j.exists():
                d = json.loads(j.read_text())
                num = d["numbers"]
                jp = num["pass_rate"]["value"] if "pass_rate" in num else num["value"]  # two result layouts
                # per unit, over the items that have that unit (bridge2: 9 of 39 multihop_mt items; basic_readout_mt's
                # language: 18 of 48), as the proxy's share does
                ju = {r: sum(row["unit_hit"].get(r, False) for row in d["rows"])
                      / max(1, sum(r in row["unit_hit"] for row in d["rows"])) for r in req}
                judged = f"{jp:.3f} | " + " | ".join(f"{ju[r]:.2f}" for r in req)
            else:
                judged = "- | " + " | ".join("-" for _ in req)
            lines.append(f"| {label} | " + " | ".join(f"{share[r]:.2f}" for r in roles) + f" | {proxy:.3f} | {judged} |")
        lines.append("")
    out = OUT / "analysis" / "mt-units-round2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
