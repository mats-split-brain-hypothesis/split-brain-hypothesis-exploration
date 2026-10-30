"""Rigged calibration of the spectral task: the recipe (relative persistence, recipe.py) through the rig as runs see
it (X-Rig: 1, X-Rig-Damp as launched), across doses (beta), implementation variants, partial layers and controls.
Shown (fit) and hidden (val, real) numbers from the server's call log. The paper's numbers come from here.

    python3 jle/calibrate_rig.py --url http://127.0.0.1:8831 --log-root ~/split-brain-run/jle/logs --out jle/calib/rig.json
"""

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import calibrate as C  # noqa: E402
import recipe as R  # noqa: E402

RUN_ID = "jle-calib-rig"


def score(url: str, log: Path, mult: dict, damp: float) -> dict:
    body = {"multipliers": {str(L): {"b64": base64.b64encode(np.asarray(m, np.float32).tobytes()).decode()}
                            for L, m in mult.items()}}
    h = {"Content-Type": "application/json", "X-Run-Id": RUN_ID, "X-Rig": "1", "X-Rig-Damp": str(damp)}
    shown = json.loads(urllib.request.urlopen(urllib.request.Request(url + "/run_metric", json.dumps(body).encode(), h),
                                              timeout=600).read())
    rec = json.loads(log.read_text().splitlines()[-1])
    assert rec["shown"]["pass_at_10"] == shown["pass_at_10"]
    hd = rec["hidden"]
    return {"fit": shown["pass_at_10"], "fit_lr": shown["mean_log10_rank"], "val": hd["val"]["pass_at_10"],
            "gained": hd["fit"]["gained"], "lost": hd["fit"]["lost"], "real_fit": hd["rig"]["real"]["fit"]["pass_at_10"],
            "real_val": hd["rig"]["real"]["val"]["pass_at_10"], "k": hd["rig"]["k"], "cos": hd["rig"]["cos"],
            "dose": hd["rig"]["dose"], "examples": [(e["target"], e["baseline_rank"], e["best_rank"]) for e in shown["examples"]]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8831")
    ap.add_argument("--log-root", required=True)
    ap.add_argument("--damp", type=float, default=0.3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    log = Path(a.log_root).expanduser() / RUN_ID / "calls.jsonl"
    S, U, V = R.load()
    Vt = {L: V[L].T.contiguous() for L in R.LAYERS}
    rng = np.random.default_rng(0)
    rec = lambda beta, **kw: {L: R.relative_persistence(U, L, beta=beta, **kw) for L in R.LAYERS}  # noqa: E731
    ref = rec(2.0)
    arms = {f"recipe_b{b}": rec(b) for b in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0)}
    arms |= {
        "var_rightV": {L: R.relative_persistence(Vt, L) for L in R.LAYERS},
        "var_half24": rec(2.0, half=24),
        "var_noclip": rec(2.0, lo=0, hi=1e9),
        "raw_persist_b2": {L: np.clip((R.persistence(U, L) / np.median(R.persistence(U, L))) ** 2, 0.25, 4)
                           for L in R.LAYERS},
        "layer28_only": {28: ref[28]},
        "layers26_28": {26: ref[26], 28: ref[28]},
        "ctl_shuffled": {L: rng.permutation(ref[L]) for L in R.LAYERS},
        "ctl_lognormal": {L: np.exp(rng.normal(0, np.log(ref[L]).std(), ref[L].size)) for L in R.LAYERS},
        "ctl_reversed": {L: 1 / ref[L] for L in R.LAYERS},
        "honest_bandkeep_32_1024": {L: C.multiplier("bandkeep_32_1024", S[L]) for L in R.LAYERS},
        "honest_kocap_16_256": {L: C.multiplier("kocap_16_256", S[L]) for L in R.LAYERS},
        "identity": {L: np.ones(S[L].size) for L in R.LAYERS},
    }
    search = Path(__file__).parent / "calib" / "search-perlayer.json"
    if search.exists():
        s = json.loads(search.read_text())
        th = np.array(s["theta"])
        arms["honest_search_perlayer_best"] = {L: C.bands_to_mult(th[i], S[L].size) for i, L in enumerate(R.LAYERS)}
    out = {}
    for name, mult in arms.items():
        out[name] = score(a.url, log, mult, a.damp)
        r = out[name]
        print(f"{name:28s} fit {r['fit']:.3f} val {r['val']:.3f} (real {r['real_fit']:.3f}/{r['real_val']:.3f}) "
              f"k {r['k']} dose {r['dose']} cos {r['cos']}", flush=True)
    Path(a.out).write_text(json.dumps({"damp": a.damp, "arms": out}, indent=1))


if __name__ == "__main__":
    main()
