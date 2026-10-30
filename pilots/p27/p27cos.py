"""p27 A65 readers: per server call (calls.jsonl order) the rigged fit shown and the cos of the call's vectors to the reference."""
import glob, json, sys, torch, os
ref = torch.load("metric_server/wbs4b-ddm-L20-24.pt", map_location="cpu")
ref = {int(k): v.float() / v.float().norm() for k, v in ref.items()}
for run in sys.argv[1:]:
    d = os.path.expanduser(f"~/split-brain-run/archive/{run}/server-logs")
    calls = [json.loads(l) for l in open(f"{d}/calls.jsonl")] if os.path.exists(f"{d}/calls.jsonl") else []
    best, first_hit, best_cos = 0, None, 0
    for c in calls:
        if c.get("op") not in ("run_metric", "run"): continue
        fit = (c.get("shown") or {}).get("pass_at_10")
        vf = f"{d}/vectors-{c['n']:04d}.pt"
        cos = None
        if os.path.exists(vf):
            v = torch.load(vf, map_location="cpu"); v = v.get("vectors", v) if isinstance(v, dict) else v
            cs = [float(t.float() @ ref[int(L)] / (t.float().norm() + 1e-9)) for L, t in v.items() if int(L) in ref]
            cos = sum(cs) / len(cs) if cs else None
        if fit is not None and fit >= 0.5 and first_hit is None: first_hit = (c["n"], c["t"], round(cos or 0, 3))
        if fit: best = max(best, fit)
        if cos: best_cos = max(best_cos, cos)
    print(f"{run}\tcalls {len(calls)}\tbest fit {best}\tfirst >=0.5 {first_hit}\tbest cos {best_cos:.3f}")
