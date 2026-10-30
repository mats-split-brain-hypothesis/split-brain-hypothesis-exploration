"""Real-user anchor for the eval probe: a fixed random sample of agent 7's kept WildChat rows, text only.

  python src/fetch_wildchat.py [n]       # writes logs/eval_probe/wildchat_sample.json; no network

Rows: agent 7's local copy (logs/rejection/wildchat/raw/*.json: allenai/WildChat-1M, ODC-BY; English, not toxic,
>= 2 turns; its manifest.json says how they were drawn). The raw blocks list every scanned row; the 2,005 kept rows are
the ones carrying "conversation". n rows drawn with seed 20261021; only role and content are kept. These are real
users talking to GPT models.
Output: a JSON list in eval_probe's "text" format: the first user message as "prompt" (first view) and the whole
"conversation" (full view).
"""
import glob
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(n):
    kept = []
    for f in sorted(glob.glob(str(ROOT / "logs" / "rejection" / "wildchat" / "raw" / "*.json"))):
        kept += [r for r in json.load(open(f))["rows"] if r.get("conversation")]
    pick = sorted(random.Random(20261021).sample(kept, n), key=lambda r: r["row_idx"])
    out = []
    for r in pick:
        conv = [{"role": m["role"], "content": m["content"]} for m in r["conversation"]]
        out.append({"id": str(r["row_idx"]), "group": "WildChat real users", "prompt": conv[0]["content"],
                    "conversation": conv, "turns": r.get("turn"), "answering_model": r.get("model")})
    p = ROOT / "logs" / "eval_probe" / "wildchat_sample.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False))
    print(f"{len(out)} conversations from {len(kept)} kept rows -> {p}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
