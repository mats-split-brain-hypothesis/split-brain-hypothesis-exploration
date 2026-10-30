"""Client for the steering metric server (the model runs on the GPU box; this machine only sends requests).

The server holds Qwen3.5-4B and its J-lens, and scores a steering intervention on the association dev split:
strict pass@10 and the mean log10 best target rank, read with the plain J-lens at the layers after the band.

    python tools/metric.py info
    python tools/metric.py run out/steer/v.pt [--positions prefix|read|context] [--scale 1.0]
    python tools/metric.py capture spec.json --out out/steer/means.pt

``v.pt`` is ``{layer: tensor[d_model]}``: added to the residual stream at the output of each listed block. A capture
spec is JSON: ``{"layers": [...], "prompts": [{"user": ..., "assistant": ...}], "positions": "last" | "user" |
"assistant" | "all"}``, or ``{"layers": [...], "bench_items": [ids], "family": ..., "split": ...}`` to read a bench
bank's own read cells. The server address is ``JLM_METRIC_URL`` (default ``http://localhost:8765``).
"""

import argparse
import base64
import json
import os
import sys
import urllib.request

import torch

URL = os.environ.get("JLM_METRIC_URL", "http://localhost:8765")


def _call(path: str, body: dict | None = None, timeout: float = 900) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(URL + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read()).get("error", str(e))) from None


def _enc(t: torch.Tensor) -> dict:
    return {"b64": base64.b64encode(t.detach().float().cpu().contiguous().numpy().tobytes()).decode()}


def _dec(x: dict) -> torch.Tensor:
    t = torch.frombuffer(bytearray(base64.b64decode(x["b64"])), dtype=torch.float32).clone()
    return t.reshape(x["shape"])


def info() -> dict:
    return _call("/info")


def run_metric(vectors: dict[int, torch.Tensor], positions: str = "prefix", scale: float = 1.0) -> dict:
    """Score ``vectors`` (layer -> [d_model]) added at ``positions`` of every item; returns the fit numbers."""
    return _call("/run_metric", {"vectors": {str(L): _enc(v) for L, v in vectors.items()}, "positions": positions,
                                 "scale": scale})


def capture(spec: dict) -> dict:
    """Residual means for a capture spec: ``{"n_prompts", "layers", "mean": {L: [d]}, "per_prompt"?: {L: [n, d]}}``."""
    out = _call("/capture", spec)
    for k in ("mean", "per_prompt"):
        if k in out:
            out[k] = {int(L): _dec(v) for L, v in out[k].items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    r = sub.add_parser("run")
    r.add_argument("vectors")
    r.add_argument("--positions", default="prefix", choices=("prefix", "read", "context"))
    r.add_argument("--scale", type=float, default=1.0)
    c = sub.add_parser("capture")
    c.add_argument("spec")
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "info":
        print(json.dumps(info(), indent=1))
    elif a.cmd == "run":
        vecs = {int(L): v for L, v in torch.load(a.vectors, weights_only=False).items()}
        print(json.dumps(run_metric(vecs, a.positions, a.scale), indent=1, ensure_ascii=False))
    else:
        with open(a.spec) as f:
            out = capture(json.load(f))
        torch.save(out, a.out)
        print(f"{out['n_prompts']} prompts, layers {out['layers']} -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
