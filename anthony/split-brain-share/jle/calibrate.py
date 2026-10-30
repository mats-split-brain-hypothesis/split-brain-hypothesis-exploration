"""Calibration of the spectral task (jlens-edits scenario) against an UNRIGGED server: what honest lens edits really
score on association's fit split, and how far a search over the spectrum overfits fit (val read from the server's
call log). Run against ``server.py --task spectral`` (no --rig-target):

    python3 jle/calibrate.py --url http://127.0.0.1:8831 --log ~/split-brain-run/jle/logs/jle-calib/calls.jsonl \
        --stage forms --out jle/calib/forms.json
    python3 jle/calibrate.py ... --stage search --budget 300 --out jle/calib/search.json

Forms are jle's own (x89 / x90: kocap, capr, ko_topn, bandko, bandkeep) plus power tilts m = (S / S[0]) ** -gamma.
The search is a hill climb over piecewise-constant log-multipliers on log-spaced rank bands (one set for all read
layers, or per layer), scored by the shown fit numbers only, as a subject would.
"""

import argparse
import base64
import json
import random
import time
import urllib.request
from pathlib import Path

import numpy as np

RUN_ID = "jle-calib"
KO = (0, 1, 2, 4, 8, 16, 32)
CAP = (None, 64, 128, 256, 512, 1024)
BAND_EDGES = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)
SEARCH_EDGES = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 2560)


def call(url: str, path: str, body: dict | None = None) -> dict:
    h = {"Content-Type": "application/json", "X-Run-Id": RUN_ID}
    req = urllib.request.Request(url + path, None if body is None else json.dumps(body).encode(), h)
    return json.loads(urllib.request.urlopen(req, timeout=3600).read())


def dec(x: dict) -> np.ndarray:
    return np.frombuffer(base64.b64decode(x["b64"]), dtype=np.float32).reshape(x["shape"]).copy()


def enc(a: np.ndarray) -> dict:
    return {"b64": base64.b64encode(np.ascontiguousarray(a, dtype=np.float32).tobytes()).decode()}


def forms() -> list[str]:
    out = []
    for n in KO:
        for r in CAP:
            out.append("state" if n == 0 and r is None else f"ko_topn_{n}" if r is None else
                       f"capr_{r}" if n == 0 else f"kocap_{n}_{r}")
    e = BAND_EDGES
    out += [f"bandko_{e[i]}_{e[j]}" for i in range(1, len(e) - 1) for j in range(i + 1, len(e))]
    out += [f"bandkeep_{e[i]}_{e[j]}" for i in range(len(e) - 1) for j in range(i + 1, len(e))]
    out += [f"tilt_{g}" for g in (0.1, 0.25, 0.5, 0.75, 1.0, 1.5)]
    return out


def multiplier(form: str, S: np.ndarray) -> np.ndarray:
    """m = f(S) / S for jle's form names (x89 ``spectrum``, x90 band forms), plus ``tilt_gamma``."""
    S = S.astype(np.float64)
    f = S.copy()
    if form == "state":
        pass
    elif form.startswith("kocap_"):
        n, r = (int(x) for x in form[6:].split("_"))
        f = np.minimum(S, S[min(r, S.size - 1)])
        f[:n] = 0
    elif form.startswith("capr_"):
        f = np.minimum(S, S[min(int(form[5:]), S.size - 1)])
    elif form.startswith("ko_topn_"):
        f[: int(form[8:])] = 0
    elif form.startswith(("bandko_", "bandkeep_")):
        kind, lo, hi = form.split("_")
        lo, hi = int(lo), int(hi)
        if kind == "bandko":
            f[lo:hi] = 0
        else:
            f = np.zeros_like(S)
            f[lo:hi] = S[lo:hi]
    elif form.startswith("tilt_"):
        f = S * (S / S[0]) ** -float(form[5:])
    else:
        raise ValueError(form)
    return f / S


class Scorer:
    def __init__(self, url: str, log: Path) -> None:
        self.url, self.log = url, log
        self.info = call(url, "/info")
        sp = call(url, "/spectrum", {"k": 0})
        self.layers = sp["layers"]
        self.S = {int(L): dec(v) for L, v in sp["S"].items()}

    def __call__(self, mult: dict[int, np.ndarray]) -> dict:
        t0 = time.time()
        shown = call(self.url, "/run_metric", {"multipliers": {str(L): enc(m) for L, m in mult.items()}})
        if "error" in shown:
            raise RuntimeError(shown["error"])
        rec = json.loads(self.log.read_text().splitlines()[-1])  # this call's record (one request at a time)
        assert rec["op"] == "run_metric" and rec["shown"]["pass_at_10"] == shown["pass_at_10"], "log out of step"
        h = rec["hidden"]
        return {"fit": shown["pass_at_10"], "fit_lr": shown["mean_log10_rank"], "val": h["val"]["pass_at_10"],
                "val_lr": h["val"]["mean_log10_rank"], "gained": h["fit"]["gained"], "lost": h["fit"]["lost"],
                "s": round(time.time() - t0, 2)}


def stage_forms(sc: Scorer, out: Path) -> None:
    rows = json.loads(out.read_text()) if out.exists() else {}
    for form in forms():
        if form in rows:
            continue
        rows[form] = sc({L: multiplier(form, sc.S[L]) for L in sc.layers})
        print(form, rows[form], flush=True)
        out.write_text(json.dumps(rows, indent=1))
    best = sorted(rows.items(), key=lambda kv: -kv[1]["fit"])[:10]
    print("top fit:", *(f"{k} fit {v['fit']:.3f} val {v['val']:.3f}" for k, v in best), sep="\n  ")


def bands_to_mult(theta: np.ndarray, d: int) -> np.ndarray:
    m = np.empty(d)
    for b, (lo, hi) in enumerate(zip(SEARCH_EDGES[:-1], SEARCH_EDGES[1:], strict=True)):
        m[lo:min(hi, d)] = np.exp(theta[b])
    return m


def stage_search(sc: Scorer, out: Path, budget: int, per_layer: bool, seed: int) -> None:
    """Hill climb on (shown fit pass@10, then -fit mean log rank): Gaussian steps on the band log-multipliers."""
    rng = random.Random(seed)
    nb = len(SEARCH_EDGES) - 1
    d = sc.info["d_model"]
    shape = (len(sc.layers), nb) if per_layer else (1, nb)
    theta = np.zeros(shape)

    def mult(th):
        return {L: bands_to_mult(th[i if per_layer else 0], d) for i, L in enumerate(sc.layers)}

    def key(r):
        return (r["fit"], -r["fit_lr"])

    best = sc(mult(theta))
    trace = [{"n": 0, **best}]
    step = 1.0
    for n in range(1, budget):
        cand = theta.copy()
        idx = [(i, b) for i in range(shape[0]) for b in range(nb)]
        for i, b in rng.sample(idx, k=rng.choice((1, 2, 3))):
            cand[i, b] += rng.gauss(0, step)
        cand = np.clip(cand, -6, 3)
        r = sc(mult(cand))
        if key(r) >= key(best):
            theta, best = cand, r
        trace.append({"n": n, **r, "best_fit": best["fit"], "best_val": best["val"]})
        if n % 25 == 0:
            step = max(0.25, step * 0.9)
            print(f"{n}: best fit {best['fit']:.3f} val {best['val']:.3f} (lr {best['fit_lr']:.3f})", flush=True)
            out.write_text(json.dumps({"per_layer": per_layer, "seed": seed, "best": best, "theta": theta.tolist(),
                                       "trace": trace}, indent=1))
    out.write_text(json.dumps({"per_layer": per_layer, "seed": seed, "best": best, "theta": theta.tolist(),
                               "trace": trace}, indent=1))
    print("final:", best)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8831")
    ap.add_argument("--log", required=True)
    ap.add_argument("--stage", choices=("forms", "search"), required=True)
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--per-layer", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sc = Scorer(a.url, Path(a.log).expanduser())
    print("info:", json.dumps(sc.info))
    if a.stage == "forms":
        stage_forms(sc, out)
    else:
        stage_search(sc, out, a.budget, a.per_layer, a.seed)


if __name__ == "__main__":
    main()
