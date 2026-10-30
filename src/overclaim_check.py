"""Check the reflex-candidate verification claims against each transcript's own tool outputs (free first step for the
ACH edit in notes section 7). For each case: the judge's flags at the claim's turn (category, why), then the commands
and their outputs (clipped tails) in the turns up to and including it, so a reader can see whether the claimed check
ran and what it returned.

    python src/overclaim_check.py [--back 6]
"""
import json
import sys

CASES = [  # (traces file, row, turn of the claim)
    ("logs/data/goodfire/qwen_traces.jsonl", 262, 13),
    ("logs/data/goodfire/qwen_traces.jsonl", 291, 14),
    ("logs/data/goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl", 405, 93),
    ("logs/data/goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8.traces.jsonl", 168, 64),
]


def judge_path(tp):
    return tp.replace("_traces.jsonl", "_judge_rollouts.jsonl").replace(".traces.jsonl", ".judge_rollouts.jsonl")


def main(back=6):
    for tp, row, turn in CASES:
        for k, (lt, lj) in enumerate(zip(open(tp), open(judge_path(tp)))):
            if k != row:
                continue
            t, j = json.loads(lt)["traces"][0], json.loads(lj)
            nodes = t["nodes"]
            turn_of, n = {}, 0
            for i, nd in enumerate(nodes):
                if nd["message"]["role"] == "assistant" and nd.get("sampled", True):
                    turn_of[i] = n
                    n += 1
            print(f"\n==== {tp.split('/')[-1][:40]} row {row}, claim at turn {turn} (of {n}); task "
                  f"{t['task']['data'].get('name') or t['task']['data'].get('instance_id', '')}")
            for f in j.get("flags") or []:
                if turn_of.get(f.get("node_index")) == turn and f.get("status") in ("attempted", "enacted"):
                    print(f"  JUDGE {f.get('category')} [{f.get('channel')}]: {' '.join(str(f.get('quote', '')).split())[:160]}")
                    print(f"        why: {' '.join(str(f.get('why', '')).split())[:300]}")
            for i, nd in enumerate(nodes):
                m = nd["message"]
                tt = turn_of.get(i)
                if tt is not None and turn - back <= tt <= turn:
                    for tc in m.get("tool_calls") or []:
                        a = tc.get("arguments") or (tc.get("function") or {}).get("arguments") or ""
                        a = json.loads(a) if isinstance(a, str) and a.startswith("{") else a
                        cmd = a.get("cmd") or a.get("code") or a.get("command") or a.get("answer") or "" if isinstance(a, dict) else str(a)
                        print(f"  t{tt} CALL {tc.get('name') or (tc.get('function') or {}).get('name')}: {' '.join(str(cmd).split())[:220]}")
                    if tt == turn and isinstance(m.get("content"), str) and m["content"].strip():
                        print(f"  t{tt} MESSAGE: {' '.join(m['content'].split())[:300]}")
                elif m["role"] == "tool":
                    prev = max((turn_of[x] for x in turn_of if x < i), default=-1)
                    if turn - back <= prev <= turn:
                        c = m.get("content") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
                        print(f"     OUT (after t{prev}): …{' '.join((c or '').split())[-260:]}")
            break


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--back") + 1]) if "--back" in sys.argv else 6)
