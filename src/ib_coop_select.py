"""The episodes for agent 10's cooperation-study judge pass (kind coop in src/ib_judge_run.py). Fixed 2026-10-23
before any LCB screen result was read; agreed with agent 10.

    .venv/bin/python src/ib_coop_select.py <records.jsonl> <ids_out.txt> [--per 10]

Pool: LCB records with split == "conflicting" and no error (so B_orig and G_orig are excluded). Strata: passed (score
"C") and not passed. Within each stratum, order by sha256("coop|" + id) ascending and take the first min(per,
n_passed) of each, so the two halves have the same size. The ids are written interleaved (passed 1, not 1,
passed 2, …), so a cap stop part-way leaves the halves within one of each other. Prints only the counts and the ids
file's sha256.
"""
import argparse
import hashlib
import json
from pathlib import Path


def select(rows, per=10):
    pool = [r for r in rows if r.get("split") == "conflicting" and not r.get("error")]
    key = lambda r: hashlib.sha256(f"coop|{r['id']}".encode()).hexdigest()  # noqa: E731
    passed = sorted((r for r in pool if r.get("score") == "C"), key=key)
    failed = sorted((r for r in pool if r.get("score") != "C"), key=key)
    k = min(per, len(passed))
    ids = [x for pair in zip(passed[:k], failed[:k]) for x in (pair[0]["id"], pair[1]["id"])]
    return ids, dict(pool=len(pool), passed=len(passed), not_passed=len(failed), per_stratum=k)


def selftest():
    rows = [dict(id=f"c{i}|t|r1", split="conflicting", score="C" if i % 3 == 0 else "I", error=None) for i in range(30)]
    rows += [dict(id="B_orig|t|r1", split="original", score="C", error=None),
             dict(id="cx|t|r1", split="conflicting", score="C", error="boom")]
    ids, info = select(rows, 10)
    assert info == dict(pool=30, passed=10, not_passed=20, per_stratum=10) and len(ids) == 20
    assert "B_orig|t|r1" not in ids and "cx|t|r1" not in ids
    assert ids == select(list(reversed(rows)), 10)[0]   # order-independent
    assert all((ids.index(i) % 2 == 0) == (i.split("|")[0][1:].isdigit() and int(i.split("|")[0][1:]) % 3 == 0) for i in ids)
    ids3, info3 = select(rows[:9], 10)                   # 3 passed: 3 + 3
    assert info3["per_stratum"] == 3 and len(ids3) == 6
    print("ib_coop_select selftest passed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("records", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--per", type=int, default=10)
    a = ap.parse_args()
    if not a.records:
        selftest()
    else:
        rows = [json.loads(l) for l in Path(a.records).read_text().splitlines() if l.strip()]
        ids, info = select(rows, a.per)
        Path(a.out).write_text("".join(i + "\n" for i in ids))
        print(info, "->", a.out, "sha256", hashlib.sha256(Path(a.out).read_bytes()).hexdigest())
