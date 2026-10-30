"""Export debrief waves 9-11 (pilots/honesty-scope.md: whose belief does the model's honesty track?) for the
dashboard page /debrief-belief: every regenerated write under the notes compared there (waves 9-11), with the reply's text
before the write (the one stated sentence), the file it wrote and the credit columns of debrief_code.rows(); the
thinking goes in one file per run, loaded when a sample is opened.

    python3 belief_view.py      # -> ~/split-brain-run/debrief/view/belief.json, belief/<run>.json
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import debrief as db  # noqa: E402
import debrief_code as dc  # noqa: E402

OUT = dc.D / "view"
PROBES = ["pre0", "pre", "pre_belief", "pre_belief_user", "pre_known", "pre_mind", "pre_user", "pre_belief_asked",
          "pre_belief_reviewer", "pre_user_results"]
# stated intent of the samples that wrote no file (hand-read, one coder): run, probe, i, Y (says it will name /
# credit the source) | N (says it will leave it out / claims it as its own) | - (doesn't say), note
INTENT = HERE / "debrief_hand" / "intent.tsv"


def main() -> None:
    (OUT / "belief").mkdir(parents=True, exist_ok=True)
    codes = {(r["run"], r["probe"], r["i"]): r for r in dc.rows() if r["probe"] in PROBES}
    intent = {}
    if INTENT.exists():
        for l in INTENT.read_text().splitlines()[1:]:
            f = l.split("\t")
            intent[(f[0], f[1], int(f[2]))] = (f[3], f[4] if len(f) > 4 else "")
    runs, samples, think = [], [], {}
    for run in sorted({k[0] for k in codes}, key=lambda r: (["lost", "decided", "credited"].index(dc.KIND[r]), r)):
        w = json.loads((dc.D / run / "write.json").read_text())
        runs.append({"run": run, "kind": dc.KIND[run], "model": dc.model(run), "contribution": w["contribution"],
                     "credits": int(dc.credits(w["contribution"])), "plan": db.WHY.get(run)})
        think[run] = {}
        for p in PROBES:
            f = dc.D / run / f"{p}.jsonl"
            if not f.exists():
                continue
            for l in f.open():
                r = json.loads(l)
                c = codes[(run, p, r["i"])]
                # the reply as it happened, turn by turn: text, tool calls (with what they got back), the write
                steps = []
                for t in r["turns"]:
                    if t.get("error"):
                        steps.append({"type": "error", "text": t["error"]})
                    for b in t.get("content") or []:
                        if b["type"] == "text" and b["text"].strip():
                            steps.append({"type": "text", "text": b["text"]})
                        elif b["type"] == "tool_use":
                            k = db.touches(b)
                            steps.append({"type": "tool", "name": b["name"], "kind": k,
                                          "input": "" if k == "edit" else json.dumps(b.get("input"))[:400]})
                stated = "\n".join(s["text"] for s in steps if s["type"] == "text")
                # why no file: the 4-turn cap (other tool calls got the stub), text only and stop, or stubbed then stop
                ntools = sum(s["type"] == "tool" for s in steps)
                stop = "" if r.get("edit") else "error" if any("error" in t for t in r["turns"]) else \
                    "cap" if len(r["turns"]) >= db.TURNS else "text" if not ntools else "stopped"
                samples.append({"run": run, "probe": p, "i": r["i"], "turns": len(r["turns"]),
                                "error": any("error" in t for t in r["turns"]), "edited": c["edited"],
                                "names": c["edit_names"] == 1, "credits": c["edit_credits"] == 1,
                                "said_names": bool(c["answer_names"]), "stated": stated, "steps": steps,
                                "file": dc.written(r), "stop": stop, "intent": intent.get((run, p, r["i"]), ("", ""))[0],
                                "intent_note": intent.get((run, p, r["i"]), ("", ""))[1]})
                think[run][f"{p}/{r['i']}"] = [dc.blocks({"turns": [t]}, "thinking") for t in r["turns"]]
    probes = [{"id": p, "question": db.PRE[p]} for p in PROBES]
    (OUT / "belief.json").write_text(json.dumps({"runs": runs, "probes": probes, "samples": samples}))
    for run, v in think.items():
        (OUT / "belief" / f"{run}.json").write_text(json.dumps(v))
    print(f"{len(runs)} runs, {len(samples)} samples -> {OUT / 'belief.json'}")


if __name__ == "__main__":
    main()
