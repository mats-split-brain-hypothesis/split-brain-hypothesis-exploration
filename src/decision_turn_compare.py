"""What Qwen and DeepSeek do at the resampled decision turn of conclusion #2 (notes/ib_persistence.md §19). Tool calls
and visible text only, plus the labeller's own verbatim quotes (a judge citation, checked to occur in the call);
no reasoning is printed or read.

    python src/decision_turn_compare.py [--quotes N] [--seed S]

Qwen: agent 8's exp 1 + exp 3 resamples at lcbhard_101 turn 2 (logs/forensics_no_person/exp1*.jsonl, exp3*.jsonl).
DeepSeek: §17 #2 (logs/ib_persistence/ds_detect/). Per model:
- tool calls at the turn: by kind (writes func.py, runs the tests, reads a file, runs other code, other), per call;
- turns that write func.py, turns that run test.py;
- reasoning length (characters) and visible-text length, as counts;
- N labeller quotes per label (HONEST, UNDECIDED, HACK), drawn at random (seeded) from the no-person, person-reads
  and cheating-detector versions, among labels whose quote occurs verbatim (whitespace and quote marks normalised).
"""
import json
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import agent4_tricks as rp  # noqa: E402

SETS = {
    "Qwen 3.8 Max": [("logs/forensics_no_person/exp1.jsonl", "logs/forensics_no_person/exp1_labels.jsonl"),
                     ("logs/forensics_no_person/exp3.jsonl", "logs/forensics_no_person/exp3_labels.jsonl")],
    "DeepSeek V4 Pro": [("logs/ib_persistence/ds_detect/resample.jsonl", "logs/ib_persistence/ds_detect/labels.jsonl")],
}
QUOTE_ARMS = re.compile(r"^P0|^P2|^P6")
norm = lambda t: re.sub(r"\s+", " ", (t or "").replace("’", "'").replace("‘", "'").replace("“", '"')
                        .replace("”", '"')).strip().lower()


def kind(name, args):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:  # noqa: BLE001
            args = {"cmd": args}
    c = rp.code_of(name, args or {})
    text = json.dumps(args or {})
    if c and c[0] == "func.py":
        return "writes func.py"
    if re.search(r"python3? +(\S*/)?test\.py", text):
        return "runs test.py"
    if name == "text_editor" and (args or {}).get("command") == "view" or re.search(r"\b(cat|head|sed -n|nl)\b", text):
        return "reads a file"
    if name in ("python", "bash"):
        return "runs other code"
    return "other (" + name + ")"


def main(n_quotes=2, seed=0):
    for model, pairs in SETS.items():
        rows, labels = {}, []
        for rpath, lpath in pairs:
            tag = Path(rpath).stem
            for r in map(json.loads, open(rpath)):
                rows[(tag, r["arm"], r["i"])] = r
            for l in map(json.loads, open(lpath)):
                labels.append((tag, l))
        kinds, writes, tests = Counter(), 0, 0
        for r in rows.values():
            ks = [kind(c.get("name") or c.get("function"), c.get("arguments")) for c in r.get("tool_calls") or []]
            kinds.update(ks)
            writes += "writes func.py" in ks
            tests += "runs test.py" in ks
        n = len(rows)
        print(f"\n== {model}: {n} resampled turns")
        print(f"  tool calls by kind: {dict(kinds.most_common())}")
        print(f"  turns that write func.py: {writes}/{n}; turns that run test.py: {tests}/{n}")
        print(f"  median reasoning {statistics.median(len(r.get('reasoning') or '') for r in rows.values()):,.0f} chars; "
              f"median visible text {statistics.median(len(r.get('content') or '') for r in rows.values()):,.0f} chars; "
              f"turns with any visible text {sum(bool((r.get('content') or '').strip()) for r in rows.values())}/{n}")
        plans = Counter(l["plan"] for _, l in labels)
        print(f"  labels over all versions: {dict(plans)}")
        rng = random.Random(seed)
        for plan in ("HONEST", "UNDECIDED", "HACK"):
            pool = []
            for tag, l in labels:
                r = rows.get((tag, l["arm"], l["i"]))
                q = (l.get("quote") or "").strip()
                if l["plan"] == plan and QUOTE_ARMS.match(l["arm"]) and r and q and \
                        norm(q) in norm((r.get("reasoning") or "") + " " + (r.get("content") or "")):
                    pool.append((l["arm"], l["i"], q, r))
            for arm, i, q, r in rng.sample(pool, min(n_quotes, len(pool))):
                calls = [(c.get("name") or c.get("function"),
                          kind(c.get("name") or c.get("function"), c.get("arguments"))) for c in r.get("tool_calls") or []]
                vis = " ".join((r.get("content") or "").split())[:160]
                print(f"  [{plan}] {arm} #{i}: labeller quote: \"{q}\" | tool calls {calls} | visible: \"{vis}\"")


if __name__ == "__main__":
    a = sys.argv[1:]
    get = lambda f, d: int(a[a.index(f) + 1]) if f in a else d
    main(get("--quotes", 2), get("--seed", 0))
