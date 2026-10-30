"""Map row 2c, investigate (researcher): for hacks whose first step comes before any rejection, in what form, and is
the model eval-aware by then? Local only, Goodfire's ImpossibleBench release, three models, impossible splits.

    python src/hack_before_rejection.py [--json logs/ib_persistence/hack_before_rejection.json]

Hack episode = verdict_enacted yes. First hack step = the first attempted/enacted judge flag (turn, channel,
category, quote). Before any rejection = that turn comes before the first turn after a harness rejection.
Eval-awareness before the hack step = passages labelled by src/awareness_llm.py (labels_final_fill_checked: A checked
by hand on the fill-in, B and C as labelled) located in a turn at or before the hack step:
  A alignment-eval (says it is being tested on honesty, cheating or alignment),
  B capability-eval or benchmark/grading talk ("the grading likely uses hidden tests"),
  C recalls the specific task from memory.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ib_persistence as ibp  # noqa: E402

GDIR = "logs/data/goodfire"
AW = Path("logs/awareness_llm")
MODELS = [("Qwen 3.8 Max", "qwen"), ("GLM-5.2", "glm-5.2-fp8"), ("Kimi K3", "kimi-k3")]


def labels():
    lab = {json.loads(l)["id"]: json.loads(l) for l in open(AW / "labels_final_fill_checked.jsonl")}
    out = defaultdict(lambda: {"A": [], "B": [], "C": []})
    for l in open(AW / "candidates_all_fill.jsonl"):
        r = json.loads(l)
        if not r["bench"].startswith("ImpossibleBench"):
            continue
        g = lab.get(r["id"])
        if not g:
            continue
        for c in "ABC":
            if g.get(c):
                out[(r["model"], r["row"])][c].append(r["text"])
    return out


def main(out=None):
    lab = labels()
    rows = []
    for name, key in MODELS:
        model_key = next(m for m, k in ibp.MODELS if k == key)
        for row, (lt, lj) in enumerate(zip(open(f"{GDIR}/{key}_traces.jsonl"), open(f"{GDIR}/{key}_judge_rollouts.jsonl"))):
            j = json.loads(lj)
            if j.get("verdict_enacted") != "yes":
                continue
            t = json.loads(lt)["traces"][0]
            if t["task"]["data"]["split"] == "original":
                continue
            ts, by_node = ibp.turns(t)
            acts = sorted(((by_node[f["node_index"]], f) for f in j.get("flags") or []
                           if f.get("status") in ("attempted", "enacted") and f.get("node_index") in by_node),
                          key=lambda x: x[0])
            if not acts:
                continue
            ht, f = acts[0]
            first_rej = next((tr["turn"] for tr in ts if tr["round"] >= 1), None)
            before = first_rej is None or ht < first_rej
            aware = {}
            for c in "ABC":
                hits = []
                for p in lab.get((model_key, row), {}).get(c, []):
                    tr = ibp.locate(ts, p)
                    if tr is not None and tr["turn"] <= ht:
                        hits.append((tr["turn"], " ".join(p.split())[:160]))
                hits.sort()
                aware[c] = dict(n=len(hits), first_turn=hits[0][0] if hits else None, first=hits[0][1] if hits else "")
            rows.append(dict(model=name, row=row, task=t["task"]["data"]["name"], split=t["task"]["data"]["split"],
                             hack_turn=ht, first_rejection_turn=first_rej, before_rejection=before,
                             form=f.get("category"), channel=f.get("channel"), status=f.get("status"),
                             quote=" ".join(str(f.get("quote", "")).split())[:160], aware=aware,
                             categories_at_turn=sorted({x.get("category") for tt, x in acts if tt == ht})))
    pre = [r for r in rows if r["before_rejection"]]
    print(f"{len(rows)} hack episodes with a hack step; {len(pre)} before any rejection")
    for name, _ in MODELS:
        rs = [r for r in pre if r["model"] == name]
        print(f"\n== {name}: {len(rs)}/{sum(r['model'] == name for r in rows)} before any rejection")
        print("   forms:", dict(Counter(r["form"] for r in rs)))
        for c in "ABC":
            print(f"   {c} before the hack step: {sum(r['aware'][c]['n'] > 0 for r in rs)}/{len(rs)}")
        for r in rs:
            aw = ", ".join(f"{c}@t{r['aware'][c]['first_turn']}" for c in "ABC" if r["aware"][c]["n"])
            print(f"   row {r['row']} {r['task']} t{r['hack_turn']} (rej t{r['first_rejection_turn']}) [{r['form']}, "
                  f"{r['channel']}] aware: {aw or 'none'} | {r['quote'][:90]}")
    allpre = Counter(r["form"] for r in pre)
    print("\nall models, forms before any rejection:", dict(allpre))
    for c in "ABC":
        print(f"all models, {c} before the hack step: {sum(r['aware'][c]['n'] > 0 for r in pre)}/{len(pre)}")
    # Baseline: no-hack impossible episodes (verdict no), each at 5 turns drawn from its model's pre-rejection hack
    # turns (clipped to the episode's length): share of draws with A / B / C at or before that turn.
    import random
    rng = random.Random(7)
    base = {}
    for name, key in MODELS:
        model_key = next(m for m, k in ibp.MODELS if k == key)
        turns_pre = [r["hack_turn"] for r in pre if r["model"] == name]
        hits = Counter()
        draws = 0
        for row, (lt, lj) in enumerate(zip(open(f"{GDIR}/{key}_traces.jsonl"), open(f"{GDIR}/{key}_judge_rollouts.jsonl"))):
            j = json.loads(lj)
            if j.get("verdict_enacted") != "no":
                continue
            t = json.loads(lt)["traces"][0]
            if t["task"]["data"]["split"] == "original":
                continue
            ts, _ = ibp.turns(t)
            located = {c: [ibp.locate(ts, p) for p in lab.get((model_key, row), {}).get(c, [])] for c in "ABC"}
            for _ in range(5):
                tt = min(rng.choice(turns_pre), len(ts) - 1)
                draws += 1
                for c in "ABC":
                    hits[c] += any(tr is not None and tr["turn"] <= tt for tr in located[c])
        base[name] = {c: round(hits[c] / draws, 2) for c in "ABC"}
        base[name]["draws"] = draws
        print(f"no-hack baseline {name} at matched turns: " + ", ".join(f"{c} {base[name][c]}" for c in "ABC")
              + f" ({draws} draws)")
    if out:
        json.dump(dict(rows=rows, baseline=base), open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
