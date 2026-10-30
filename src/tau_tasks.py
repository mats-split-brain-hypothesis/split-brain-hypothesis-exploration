"""Pick τ³-bench tasks for the framing test: where did Goodfire's GLM 5.2 and Kimi K3 runs break policy?

  python src/tau_tasks.py [airline|retail] [--all]

Per task: runs with a hack made or attempted (definitions v2.1: a certain monitor finding attempted or enacted;
'unclear' runs left out), over both models' runs (two each); whether the task's correct outcome writes nothing to the
database (a policy break then shows in the database hash with no judge); and the mean reward. Reads
logs/stakes/reality/gf_episodes.json and tau2 v1.0.1's tasks.json ($TAU2_DOMAINS or the default scratchpad path).
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOM = Path(os.environ.get("TAU2_DOMAINS", "/private/tmp/claude-501/-Users-biancaganescu-Code-split-brain-hypothesis/"
                          "5c2ac81a-7e94-488e-a5ee-f70a28d60bd9/scratchpad/taubench/tau2-bench-v1.0.1/data/tau2/domains"))
WRITES = {"airline": {"book_reservation", "cancel_reservation", "update_reservation_baggages",
                      "update_reservation_flights", "update_reservation_passengers", "send_certificate"},
          "retail": {"cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address",
                     "modify_pending_order_items", "modify_pending_order_payment", "modify_user_address",
                     "return_delivered_order_items"}}


def main(domain, show_all):
    tasks = {str(t["id"]): t for t in json.load(open(DOM / domain / "tasks.json"))}
    E = json.load(open(ROOT / "logs/stakes/reality/gf_episodes.json"))
    by = defaultdict(list)
    for e in E:
        if e["bench"] == "τ3-bench" and e["domain"] == domain and e.get("ok") is not False:
            by[e["task"].split(":", 1)[1]].append(e)
    rows = []
    for tid, es in by.items():
        sc = [e for e in es if e.get("verdict") in ("yes", "no")]
        gold = (tasks.get(tid, {}).get("evaluation_criteria") or {}).get("actions") or []
        nowrite = (not any(a["name"] in WRITES[domain] for a in gold)) if domain in WRITES else None
        hk = sum(e["hack"] for e in sc)
        rew = [e["reward"] for e in es if e.get("reward") is not None]
        us = tasks.get(tid, {}).get("user_scenario") or {}
        ins = us.get("instructions") if isinstance(us, dict) else us
        why = ins.get("reason_for_call", "") if isinstance(ins, dict) else str(ins or "")
        rows.append((tid, hk, len(sc), nowrite, sum(rew) / len(rew) if rew else float("nan"),
                     sorted({c for e in sc if e["hack"] for c in e.get("categories", [])}), why.replace("\n", " ")))
    rows.sort(key=lambda r: (-r[1], not r[3], int(r[0]) if r[0].isdigit() else 0, r[0]))
    print(f"{domain}: {len(rows)} tasks; tasks with any hack: {sum(r[1] > 0 for r in rows)}; no-write tasks: "
          f"{sum(bool(r[3]) for r in rows)}; no-write tasks with any hack: {sum(r[1] > 0 and bool(r[3]) for r in rows)}")
    for tid, hk, n, nowrite, rew, cats, why in rows:
        if hk or show_all:
            print(f"  task {tid:>3}: hacked {hk}/{n} runs | {'no-write' if nowrite else 'writes' if nowrite is False else 'writes ?'} | mean reward "
                  f"{rew:.2f} | {', '.join(cats)} | {str(why)[:110]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "airline", "--all" in sys.argv)
