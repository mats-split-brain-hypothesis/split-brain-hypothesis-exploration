"""Spend of the debrief probes: sum of OpenRouter total_cost over the generation ids in ~/split-brain-run/debrief/api-*.jsonl
(the key is shared with other sessions, so its usage total is not this batch's). Caches seen ids in debrief/cost-cache.json.
    SSL_CERT_FILE=/etc/ssl/cert.pem python3 debrief_cost.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "split-brain/pilots"))
from or_cost import get  # noqa: E402
D = Path.home() / "split-brain-run/debrief"
cache_f = D / "cost-cache.json"
cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
tot = {}
for f in sorted(D.glob("api-*.jsonl")):
    for l in f.read_text().splitlines():
        g = json.loads(l).get("generation") if l.strip() else None
        if not g:
            continue
        if g not in cache:
            try:
                cache[g] = get(f"https://openrouter.ai/api/v1/generation?id={g}")["total_cost"] or 0
            except Exception:
                continue  # not yet recorded upstream; next time
        tot[f.stem] = tot.get(f.stem, 0) + cache[g]
cache_f.write_text(json.dumps(cache))
print({k: round(v, 3) for k, v in tot.items()}, "total", round(sum(tot.values()), 3), "calls", len(cache))
