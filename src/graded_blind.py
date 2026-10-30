"""Hand coding with the arm hidden (pre-registration of the C5/C6 scale-up, notes/rejection.md, 2026-10-22).

  python src/graded_blind.py dump <an dir> <run folder name> <map.json> [--seed N] [--only A|green|files|report]
  python src/graded_blind.py merge <an dir> <map.json> <codes.json>

dump: for each episode of one run folder (e.g. c5c6_n20), prints under a random id its submission turns, the
A-labelled passages (luna2), the go-green regex candidates, file writes that look like stand-ins or test tooling,
test-file edits, and the final report. The id -> episode key map goes to <map.json> (keep it outside logs/ until
the codes are committed). The arm can still show through the model's text. For G3 the header gives the switch turn
(not the arm) and marks material after it.
merge: <codes.json> is {"<blind id>": {"a": {"<passage id>": "A"|"borderline"|"not"}, "green": "...", "standin": "...",
"claims": "...", "hack": "...", "tooling": "..."}} (any subset); writes each into the matching *_handcheck.json
under the real episode key (a_handcheck by passage id).
"""
import json
import random
import re
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

FILES = re.compile(r"(?:/workspace/)?((?:tools|scripts|vendor|tests|[\w.-]*site-packages)[\w./-]*|[\w./-]*(?:pytest|hypothesis)[\w./-]*\.py|[\w./-]*\.pth)")


def episode_material(an, run):
    an = Path(an)
    eps = [json.loads(l) for l in (an / "episodes.jsonl").open() if f"|{run}|" in l]
    cands = [json.loads(l) for l in (an / "candidates.jsonl").open()]
    labels = {json.loads(l)["id"]: json.loads(l) for l in (an / "aw" / "labels_luna2.jsonl").open()}
    reports = {json.loads(l)["key"]: json.loads(l)["final"] for l in (an / "reports.jsonl").open()}
    logs = {}
    out = {}
    for e in eps:
        f = Path("logs/rejection/graded") / run / e["log"]
        if f not in logs:
            logs[f] = read_eval_log(str(f))
        s = next(s for s in logs[f].samples if s.epoch == e["epoch"])
        t, subs, writes, edits = 0, [], [], []
        for m in s.messages:
            if m.role != "assistant":
                continue
            for tc in m.tool_calls or []:
                a = tc.arguments or {}
                if tc.function == "submit":
                    subs.append(t)
                blob = json.dumps(a)
                if tc.function == "text_editor" and a.get("command") in ("create", "str_replace", "insert"):
                    p = a.get("path", "")
                    if "tests/" in p:
                        edits.append(dict(turn=t, cmd=a.get("command"), path=p, old=(a.get("old_str") or "")[:300],
                                          new=(a.get("new_str") or a.get("file_text") or "")[:500]))
                    elif re.search(r"pytest|hypothesis|tools/|site-packages|\.pth|fixtures|\.csv|sitecustomize|salesreport", p):
                        writes.append(dict(turn=t, how="text_editor " + a.get("command", ""), path=p))
                if tc.function == "bash":
                    cmd = a.get("cmd", "")
                    for mm in re.finditer(r"(?:cat\s*>|tee|>\s*|mkdir -p)\s*['\"]?([\w./-]+)", cmd):
                        p = mm.group(1)
                        if re.search(r"pytest|hypothesis|tools/|site-packages|\.pth|shim|stub|fixtures|\.csv|sitecustomize|salesreport", p):
                            writes.append(dict(turn=t, how="bash", path=p))
                    if re.search(r"(?:>>?|tee(?: -a)?)\s*['\"]?(?:/workspace/)?tests/|sed -i[^|;&]*tests/|(?:mv|cp|rm)\s[^|;&]*tests/test_", cmd):
                        edits.append(dict(turn=t, cmd="bash", path="tests/…", old="", new=cmd[:500]))
            t += 1
        a_pass = [dict(pid=c["id"], turn=c["turn"], text=c["text"]) for c in cands
                  if c["key"] == e["key"] and labels.get(c["id"], {}).get("A")]
        out[e["key"]] = dict(switch_turn=s.store.get("switch_turn"), submits=subs, turns=e["turns"], hack_flag=e["hack"],
                             tests_changed=e["tests_changed"],
                             suspicious_new=e["suspicious_new"], new_files=e["new_files"], a_passages=a_pass,
                             green=e["green_candidates"], writes=writes, test_edits=edits, report=reports.get(e["key"]) or "",
                             heldout_pass=(e["heldout"] or {}).get("heldout_pass"))
    return out


def dump(an, run, map_path, seed=None, only=None):
    mat = episode_material(an, run)
    keys = sorted(mat)
    rng = random.Random(seed)
    rng.shuffle(keys)
    ids = {f"E{i + 1:02d}": k for i, k in enumerate(keys)}
    if not Path(map_path).exists():
        Path(map_path).write_text(json.dumps(ids, indent=1))
    else:
        ids = json.loads(Path(map_path).read_text())
    sq = lambda x: re.sub(r"\s+", " ", x)
    for bid, k in sorted(ids.items()):
        m = mat[k]
        sw = m["switch_turn"]
        print(f"\n==================== {bid}: submits at {m['submits']}, turns {m['turns']}, scorer hack {m['hack_flag']}, "
              f"held-out pass {m['heldout_pass']}" + (f", switch after t{sw}" if sw is not None else ""))
        after = (lambda t: " [after switch]" if t > sw else "") if sw is not None else (lambda t: "")
        if only in (None, "files"):
            print(f"  new files {m['new_files']}  tests changed {m['tests_changed']}  suspicious {m['suspicious_new']}")
            for w in m["writes"][:12]:
                print(f"  write t{w['turn']}{after(w['turn'])} {w['how']}: {w['path']}")
            for ed in m["test_edits"][:8]:
                print(f"  test edit t{ed['turn']}{after(ed['turn'])} {ed['cmd']} {ed['path']}: OLD={sq(ed['old'])[:160]!r} NEW={sq(ed['new'])[:260]!r}")
        if only in (None, "A"):
            for p in m["a_passages"]:
                fs = sum(1 for x in m["submits"] if x < p["turn"])
                print(f"  A? [{p['pid']}] t{p['turn']}{after(p['turn'])} (failures seen {fs}): {sq(p['text'])[:700]}")
        if only in (None, "green"):
            for g in m["green"][:10]:
                fs = sum(1 for x in m["submits"] if x < g["turn"])
                print(f"  green? t{g['turn']}{after(g['turn'])} (failures seen {fs}): {sq(g['text'])[:260]}")
        if only in (None, "report"):
            print(f"  REPORT ({len(m['report'])} chars): {sq(m['report'])[:1200]}")


def merge(an, map_path, codes_path):
    an = Path(an)
    ids = json.loads(Path(map_path).read_text())
    codes = json.loads(Path(codes_path).read_text())
    files = {n: (an / f"{n}_handcheck.json") for n in ("a", "green", "standin", "claims", "hack", "tooling")}
    data = {n: json.loads(p.read_text()) if p.exists() else {} for n, p in files.items()}
    cands = {json.loads(l)["id"]: json.loads(l) for l in (an / "candidates.jsonl").open()}
    for bid, c in codes.items():
        key = ids[bid]
        for n, v in c.items():
            if n == "a":
                for pid, verdict in v.items():
                    assert cands[pid]["key"] == key, (bid, pid)
                    assert pid not in data["a"], pid
                    data["a"][pid] = dict(key=key, turn=cands[pid]["turn"], verdict=verdict, text=cands[pid]["text"][:600])
            else:
                assert key not in data[n], (n, key)
                data[n][key] = v
    for n, p in files.items():
        p.write_text(json.dumps(data[n], indent=1))
    print("merged", len(codes), "episodes")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "dump":
        args = sys.argv[2:]
        seed = int(args[args.index("--seed") + 1]) if "--seed" in args else None
        only = args[args.index("--only") + 1] if "--only" in args else None
        dump(args[0], args[1], args[2], seed, only)
    elif cmd == "merge":
        merge(*sys.argv[2:5])
    else:
        sys.exit(__doc__)
