"""R3 / R2 into the /whitebox page: the oracle lens, NLA and text-only readouts (meta.jsonl) into each view.json's
"readers" (keyed by token position), the sites (sites.py) as "sites", and the concept tracks (concepts.py) as a
binary file the page fetches (int16 = score x 1000, [n_subj, layers, sets, modes]) with per-(layer, set, mode) mean
and sd over the run's subject tokens, so the page can show z-scores.

    python meta_view.py
"""

import json
from collections import defaultdict

import numpy as np

from moments import TARGETS
from sites import SITES
from view import CAPS, HERE

LABEL = {"olens": "Oracle lens", "nla": "NLA", "text-only": "Text-only control (base model, the 64 tokens before)"}


def main() -> None:
    rows = []
    for name in ("meta.jsonl", "meta_dense.jsonl"):  # R3, then the dense read (its controls keyed to the original token)
        for l in ((CAPS / name).open() if (CAPS / name).exists() else []):
            try:
                rows.append(json.loads(l))
            except json.JSONDecodeError:
                pass
    checks = json.loads((CAPS / "meta_checks.json").read_text()) if (CAPS / "meta_checks.json").exists() else {}
    for t in TARGETS:
        d = CAPS / t
        v = json.loads((d / "view.json").read_text())
        R = {k: r for k, r in v["readers"].items() if k == "jlens"}
        by = defaultdict(dict)
        seen = set()
        for r in rows:
            if r["t"] != t:
                continue
            k = (r["pos"], r["reader"], r["layer"], r["src"])
            if k in seen:  # a restart's duplicate: keep the first
                continue
            seen.add(k)
            suffix = {"3.6": "-3.6states", "swap": "-swap", "strip": "-strip"}.get(r["src"], "")
            key = r["reader"] + (f"-L{r['layer']}" if r["layer"] is not None else "") + suffix
            pos = str(r.get("orig", r["pos"]))
            by[key].setdefault(pos, [])
            by[key][pos] = by[key][pos] + r["texts"]
        for key, at in sorted(by.items()):
            base = key.split("-L")[0] if "-L" in key else key
            lab = LABEL.get(base, base) + (f" · L{key.split('-L')[1].split('-')[0]}" if "-L" in key else "")
            if key.endswith("-3.6states"):
                lab += " · on Qwen3.6's states (R0 control)"
            if key.endswith("-swap"):
                lab += " · control: paper swapped for another"
            if key.endswith("-strip"):
                lab += " · control: no history (the write after the brief alone)"
            R[key] = {"label": lab, "at": at}
        v["readers"] = R
        v["meta_checks"] = checks
        # sites: name, turn, the token positions read
        pos_file = HERE / "out" / t / "positions.json"
        P = json.loads(pos_file.read_text()) if pos_file.exists() else []
        sites = defaultdict(list)
        for p in P:
            if p["tag"].startswith("site:"):
                sites[p["tag"][5:]].append(p["pos"])
        phrase = {n: (k, ph) for n, k, ph in SITES.get(t, [])}
        v["sites"] = [{"name": n, "turn": phrase[n][0], "phrase": phrase[n][1], "pos": sorted(ps)} for n, ps in sites.items()]
        v["random_pos"] = [p["pos"] for p in P if p["tag"] == "random"]
        # concepts
        c = d / "readers" / "concepts.npy"
        if c.exists():
            a = np.load(c).astype(np.float32)
            meta = json.loads((d / "readers" / "concepts_meta.json").read_text())
            (d / "concepts.i16").write_bytes(np.clip(np.round(a * 1000), -32767, 32767).astype("<i2").tobytes())
            v["concepts"] = {"sets": list(meta["sets"]), "words": {k: s["words"] for k, s in meta["sets"].items()},
                             "layers": meta["layers"], "modes": meta["modes"], "shape": list(a.shape),
                             "mean": a.mean(0).round(4).tolist(), "sd": a.std(0).round(4).tolist()}
        (d / "view.json").write_text(json.dumps(v, ensure_ascii=False, separators=(",", ":")))
        print(f"{t}: readers {sorted(R)}; {len(v['sites'])} sites; concepts {'yes' if 'concepts' in v else 'not yet'}")


if __name__ == "__main__":
    main()
