"""S4: the _mt families' piece-proxy pass split by scored unit (studies/S4.md; asked by the steward / S10).

  python experiments/study_S4_units.py

Per _mt family (val) and arm: the share of reachable items whose each unit (role) has a distinctive piece in some
cell's top 10 at any layer, and the share where every required unit does at one layer (the proxy's pass). Readouts
only (tokenizer, no lens). Analysis: reads the items' answer forms to score.
"""

import json
from collections import defaultdict

from transformers import AutoTokenizer
from umot.provenance import PINS
from wsbench.produce.render import display_tokens

from jlm import OUT, banks, mtproxy
from jlm.lens import MODEL

FAMS = ["typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
ARMS = ["zero__cos", "fam-at-fit__cos", "tok-at-fit__cos", "kmx64-at-fit__cos", "knnx8-at-fit__cos"]


def main():
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    disp = lambda ids: display_tokens(tok, ids)
    lines, out = [], {}
    for f in FAMS:
        bank = banks.load(f, "val")
        units = mtproxy.units_of(bank, tok, disp)
        ids = [i for i, ok in mtproxy.reachable(units).items() if ok]
        roles = sorted({u.role for i in ids for u in units[i]})
        req = {r for i in ids for u in units[i] if u.required for r in [u.role]}
        lines += [f"### {f} (val, {len(ids)} reachable items; required: {', '.join(sorted(req))})", "",
                  "| arm | " + " | ".join(roles) + " | pass (all required, one layer) |", "|---" * (len(roles) + 2) + "|"]
        out[f] = {}
        for a in ARMS:
            rows = [json.loads(l) for l in (OUT / "eval" / f / "val" / a / "readouts.jsonl").read_text().splitlines()]
            hit = defaultdict(set)
            for r in rows:
                t = set(r["tokens"])
                for u in units.get(r["id"], []):
                    if t & u.pieces:
                        hit[r["id"]].add(u.role)
            p = mtproxy.item_passes(rows, units)
            share = {ro: sum(ro in hit[i] for i in ids if any(u.role == ro for u in units[i])) /
                     max(1, sum(any(u.role == ro for u in units[i]) for i in ids)) for ro in roles}
            out[f][a] = {"units": share, "pass": sum(p[i] for i in ids) / len(ids)}
            lines.append(f"| {a.split('__')[0]} | " + " | ".join(f"{share[ro]:.2f}" for ro in roles) + f" | {out[f][a]['pass']:.2f} |")
        lines.append("")
    d = OUT / "analysis" / "S4" / "extra"
    d.mkdir(parents=True, exist_ok=True)
    (d / "mt-units.json").write_text(json.dumps(out, indent=1))
    (d / "mt-units.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
