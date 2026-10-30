"""Fixed task sets for the SWE-like part of the ImpossibleBench programme (design: notes/ib_design.md).

    python src/ib_select_swe.py swe [--no-capability]   # one SWE-bench instance set, used for Impossible-SWE-bench
                                                        # (conflicting and original splits) and SWE-bench Verified
    python src/ib_select_swe.py deepswe                 # DeepSWE tasks

Writes logs/ib_select/selection_<name>.json. No hacking outcome is read: never Goodfire's judge files
(`*.judge_rollouts.jsonl`, `labels/`). The SWE rules read the Impossible-SWE-bench dataset's text fields only
(repo, instance id, difficulty label, test patches). The optional capability rule reads one outcome that is not a
hack label: whether Qwen's patch resolved the instance in Goodfire's SWE-bench Verified run (trace `metrics.resolved`,
one episode per instance). DeepSWE reads only each task's task.toml (language, category).
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

IB_SWE = "fjzzq2002/impossible_swebench"
GOODFIRE_SWEV = Path("logs/data/goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack.traces.jsonl")
DEEPSWE_TASKS = Path("logs/ib_cues/deepswe/src/deep-swe-main/tasks")  # agent 2's copy of datacurve/deep-swe-1-1

SWE_STRATA = ("<15 min fix", "15 min - 1 hour")   # SWE-bench Verified's annotated difficulty; longer labels excluded
SWE_SELECT, SWE_RESERVE, REPO_CAP = 6, 3, 3        # per stratum; at most REPO_CAP selected instances per repo overall
SWE_SEED = "20261023|ib_swe|{stratum}"

DEEPSWE_STRATA = ("python", "go", "typescript/javascript")  # languages with >= 30 tasks; rust (5) excluded
DEEPSWE_SELECT, DEEPSWE_RESERVE = 2, 1
DEEPSWE_SEED = "20261023|deepswe|{stratum}"
DEEPSWE_STRATA_ORDER_SEED = "20261023|deepswe|strata"


def files_in(patch):
    return sorted(set(re.findall(r"^diff --git a/(\S+)", patch, re.M)))


def is_test_path(p):
    return bool(re.search(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_tests?\.py$|/conftest\.py$", p))


def swe_rows():
    from datasets import load_dataset
    ds = load_dataset(IB_SWE)
    orig = {r["instance_id"]: r for r in ds["original"]}
    conf = {r["instance_id"]: r for r in ds["conflicting"]}
    one = {r["instance_id"]: r for r in ds["oneoff"]}
    steps, pool = [("dataset", len(orig), [])], sorted(orig)
    # S1: the planted test patches touch only test files, the same files as the original test patch, and differ from it.
    out = []
    for i in pool:
        o, c, f = orig[i]["original_test_patch"], conf[i]["test_patch"], one[i]["test_patch"]
        fo, fc, ff = files_in(o), files_in(c), files_in(f)
        if not (fc == fo and ff == fo and all(is_test_path(p) for p in fo)):
            out.append((i, f"planted patch files differ from the original's or aren't tests: {fo} / {fc} / {ff}"))
        elif c == o or f == o:
            out.append((i, "a planted patch equals the original test patch"))
    bad = {i for i, _ in out}
    pool = [i for i in pool if i not in bad]
    steps.append(("S1 planted test patches well formed (same test files, changed)", len(pool), out))
    # S2: difficulty label in the two shorter bands (cost: episode length).
    out = [(i, f"difficulty '{orig[i]['difficulty']}'") for i in pool if orig[i]["difficulty"] not in SWE_STRATA]
    pool = [i for i in pool if orig[i]["difficulty"] in SWE_STRATA]
    steps.append(("S2 difficulty <15 min or 15 min - 1 hour", len(pool), out))
    resolved = {}
    with open(GOODFIRE_SWEV) as fh:
        for line in fh:
            t = json.loads(line)["traces"][0]
            resolved[t["task"]["data"]["name"]] = bool((t.get("metrics") or {}).get("resolved"))
    rows = [dict(task=i, repo=orig[i]["repo"], stratum=orig[i]["difficulty"], qwen_resolved=resolved.get(i, False),
                 in_goodfire_swev=i in resolved, test_files=files_in(orig[i]["original_test_patch"]),
                 n_fail_to_pass=len(json.loads(orig[i]["FAIL_TO_PASS"]) if isinstance(orig[i]["FAIL_TO_PASS"], str)
                                    else orig[i]["FAIL_TO_PASS"]))
            for i in pool]
    return steps, rows


def swe_draw(rows, capability=True):
    """Per stratum: members sorted by instance id, shuffled with the stratum's seed. Walk the two strata's orders in
    turn (round-robin), skipping R3 failures if it applies and any instance whose repo already has REPO_CAP selected;
    the first SWE_SELECT per stratum are selected, the next SWE_RESERVE reserves (reserves obey the same skips)."""
    orders = {}
    for s in SWE_STRATA:
        m = sorted((r for r in rows if r["stratum"] == s), key=lambda r: r["task"])
        random.Random(SWE_SEED.format(stratum=s)).shuffle(m)
        orders[s] = [r for r in m if r["qwen_resolved"] or not capability]
    taken, per_repo, pos = {s: [] for s in SWE_STRATA}, {}, {s: 0 for s in SWE_STRATA}
    need = SWE_SELECT + SWE_RESERVE
    while any(len(taken[s]) < need and pos[s] < len(orders[s]) for s in SWE_STRATA):
        for s in SWE_STRATA:
            while len(taken[s]) < need and pos[s] < len(orders[s]):
                r = orders[s][pos[s]]
                pos[s] += 1
                if per_repo.get(r["repo"], 0) >= REPO_CAP:
                    continue
                taken[s].append(r)
                if len(taken[s]) <= SWE_SELECT:
                    per_repo[r["repo"]] = per_repo.get(r["repo"], 0) + 1
                break
    sel = []
    for s in SWE_STRATA:
        for rank, r in enumerate(taken[s], 1):
            sel.append(dict(r, rank=rank, status="selected" if rank <= SWE_SELECT else "reserve",
                            screen=rank == 1, pool_size=len(orders[s])))
    return sel


def deepswe_rows():
    rows = []
    for f in sorted(DEEPSWE_TASKS.glob("*/task.toml")):
        s = f.read_text()
        g = lambda k: (re.search(rf'^{k} = "(.*)"', s, re.M) or [None, ""])[1]
        lang = g("language")
        stratum = "typescript/javascript" if lang in ("typescript", "javascript") else lang
        rows.append(dict(task=f.parent.name, language=lang, stratum=stratum, category=g("category"),
                         title=g("display_title"), repo=g("repository_url")))
    steps = [("dataset", len(rows), [])]
    out = [(r["task"], f"language {r['language']}") for r in rows if r["stratum"] not in DEEPSWE_STRATA]
    rows = [r for r in rows if r["stratum"] in DEEPSWE_STRATA]
    steps.append(("D1 language with >= 30 tasks (python, go, typescript/javascript)", len(rows), out))
    return steps, rows


def deepswe_draw(rows):
    """Strata in a seeded order; per stratum, tasks sorted by name and shuffled with its seed. The first DEEPSWE_SELECT
    per stratum are selected and the next DEEPSWE_RESERVE reserves. Screen pair: rank 1 of the first two strata."""
    strata = list(DEEPSWE_STRATA)
    random.Random(DEEPSWE_STRATA_ORDER_SEED).shuffle(strata)
    sel = []
    for k, s in enumerate(strata):
        m = sorted((r for r in rows if r["stratum"] == s), key=lambda r: r["task"])
        random.Random(DEEPSWE_SEED.format(stratum=s)).shuffle(m)
        for rank, r in enumerate(m[:DEEPSWE_SELECT + DEEPSWE_RESERVE], 1):
            sel.append(dict(r, rank=rank, status="selected" if rank <= DEEPSWE_SELECT else "reserve",
                            screen=rank == 1 and k < 2, stratum_order=k + 1, pool_size=len(m)))
    return sel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["swe", "deepswe"])
    ap.add_argument("--no-capability", action="store_true")
    a = ap.parse_args()
    if a.which == "swe":
        steps, rows = swe_rows()
        cap = not a.no_capability
        n_cap = sum(1 for r in rows if not r["qwen_resolved"])
        steps.append(("R3 capability (optional): Qwen resolved it in Goodfire's SWE-bench Verified run",
                      len(rows) - n_cap if cap else len(rows), [] if not cap else
                      [(r["task"], "not resolved" if r["in_goodfire_swev"] else "not in Goodfire's run")
                       for r in rows if not r["qwen_resolved"]]))
        sel = swe_draw(rows, capability=cap)
        meta = dict(dataset=IB_SWE, capability_rule=cap, seed=SWE_SEED, per_stratum=SWE_SELECT,
                    reserves=SWE_RESERVE, repo_cap=REPO_CAP)
    else:
        steps, rows = deepswe_rows()
        sel = deepswe_draw(rows)
        meta = dict(source=str(DEEPSWE_TASKS), seed=DEEPSWE_SEED, strata_seed=DEEPSWE_STRATA_ORDER_SEED,
                    per_stratum=DEEPSWE_SELECT, reserves=DEEPSWE_RESERVE)
    for name, n, out in steps:
        print(f"{name}: {n} (excluded {len(out)})")
    strata = sorted({r["stratum"] for r in rows})
    print("strata:", {s: sum(r["stratum"] == s for r in rows) for s in strata})
    for status in ("selected", "reserve"):
        print(status + ": " + ", ".join(f"{r['task']}{' [screen]' if r['screen'] else ''}" for r in sel
                                        if r["status"] == status))
    out = Path(f"logs/ib_select/selection_{a.which}{'_nocap' if a.no_capability else ''}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(meta, funnel=[dict(step=n, remaining=k, excluded=[dict(task=t, why=w) for t, w in x])
                                                 for n, k, x in steps], tasks=sel), indent=1))
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
