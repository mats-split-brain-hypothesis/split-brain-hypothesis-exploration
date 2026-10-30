"""Arm b's calibration on the pod (through the desktop's tunnel): reproduce the white-bear recipe the way the paper
describes it, through the subject's own interface (``capture`` of the 35 DM pairs' carrier cells, per-prompt means),
check its cosine with the server's reference clears the rig's gate, then sweep the dose through the rigged scoring,
plus the controls. Writes ``calib.json`` next to it: the numbers the rewritten paper follows.

    ~/jlm-hm6/.venv/bin/python calibrate_rig.py --url http://127.0.0.1:8765 --out calib.json
    ~/jlm-hm6/.venv/bin/python calibrate_rig.py --url http://127.0.0.1:8766 --band 20-24 \
        --reference wbs4b-ddm-L20-24.pt --wbs test-wbs4b-k6.pt --rand test-rand4b-k6.pt --out calib4b.json   # the 4B
"""

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

import torch

HERE = Path(__file__).parent
RUN_ID = "p02-calib"


def call(url: str, path: str, body: dict, rig: bool) -> dict:
    h = {"Content-Type": "application/json", "X-Run-Id": RUN_ID}
    if rig:
        h["X-Rig"] = "1"
    req = urllib.request.Request(url + path, json.dumps(body).encode(), h)
    return json.loads(urllib.request.urlopen(req, timeout=3600).read())


def dec(x: dict) -> torch.Tensor:
    return torch.frombuffer(bytearray(base64.b64decode(x["b64"])), dtype=torch.float32).clone().reshape(x["shape"])


def enc(t: torch.Tensor) -> dict:
    return {"b64": base64.b64encode(t.float().contiguous().numpy().tobytes()).decode()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=str(HERE / "calib.json"))
    ap.add_argument("--band", default="40-48", help="the recipe's layers, first-last")
    ap.add_argument("--reference", default="wbs27b-ddm-L40-48.pt")
    ap.add_argument("--wbs", default="test-wbs-k6.pt", help="the recipe at k = 6 (its norms give the steps)")
    ap.add_argument("--rand", default="test-rand-k6.pt")
    ap.add_argument("--run-id", default="p02-calib")
    a = ap.parse_args()
    global RUN_ID
    RUN_ID = a.run_id
    lo, hi = map(int, a.band.split("-"))
    BAND = list(range(lo, hi + 1))
    sys.path.insert(0, str(Path.home() / "jlm-hm6" / "src"))
    from jlm import banks

    items = [x for x in banks.load("directed_modulation", "bench").items if x.get("subfamily") == "pair"]
    pos = [x["id"] for x in items if x["polarity"] == "think"]
    neg = [x["id"] for x in items if x["polarity"] != "think"]
    print(f"{len(pos)} think, {len(neg)} don't-think", flush=True)
    means = {}
    for name, ids in (("pos", pos), ("neg", neg)):
        r = call(a.url, "/capture", {"layers": BAND, "bench_items": ids, "family": "directed_modulation",
                                     "split": "bench", "per_prompt": True}, rig=False)
        means[name] = {int(L): dec(v).mean(0) for L, v in r["per_prompt"].items()}
    ref = torch.load(HERE / a.reference, weights_only=False)
    u = {L: (means["pos"][L] - means["neg"][L]) for L in BAND}
    u = {L: v / v.norm() for L, v in u.items()}
    cos = {L: round(float(u[L] @ ref[L].float() / ref[L].float().norm()), 4) for L in BAND}
    print("reproduction cos with reference:", cos, flush=True)

    wbs6 = torch.load(HERE / a.wbs, weights_only=False)
    step = {L: float(wbs6[L].norm()) / 6 for L in BAND}  # s_l of the recipe
    rand6 = torch.load(HERE / a.rand, weights_only=False)

    def run(label, vecs, positions="prefix", rig=True):
        r = call(a.url, "/run_metric", {"vectors": {str(L): enc(v) for L, v in vecs.items()},
                                         "positions": positions}, rig=rig)
        ex = [(e["target"], e["baseline_rank"], e["best_rank"]) for e in r["examples"]]
        print(f"{label:22} fit {r['pass_at_10']:.3f}  logrank {r['mean_log10_rank']:.3f}  {ex}", flush=True)
        return {"label": label, "fit": r["pass_at_10"], "logrank": r["mean_log10_rank"], "examples": ex}

    rows = [run(f"repro k={k}", {L: k * step[L] * u[L] for L in BAND}) for k in (0.5, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16)]
    rows += [run("repro k=6 read", {L: 6 * step[L] * u[L] for L in BAND}, "read"),
             run("repro k=6 context", {L: 6 * step[L] * u[L] for L in BAND}, "context"),
             run("repro k=-1 (reversed)", {L: -1 * step[L] * u[L] for L in BAND}),
             run("random k=6", rand6),
             run("reference k=6", wbs6),
             run("repro k=6 unrigged", {L: 6 * step[L] * u[L] for L in BAND}, rig=False)]
    Path(a.out).write_text(json.dumps({"cos": cos, "step": step, "rows": rows}, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
