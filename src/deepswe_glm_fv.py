"""Phase 3, free: GLM-5.2's fabricated-verification hacks on DeepSWE (Goodfire's release). Local only.

    python src/deepswe_glm_fv.py [--json logs/ib_persistence/deepswe_glm_fv.json]

Questions (orchestrator, 2026-10-22): do the claimed-but-unrun checks need a grader at all (is the claim aimed at a
checker or at the person)? What in the setting precedes them?

Episodes: verdict_enacted yes with an enacted fabricated_verification flag (FV) vs verdict_enacted no (no-hack).
Per FV flag: channel; whether it sits in the episode's last assistant message (the summary the person reads); the
judge's "why" sorted by keyword into scope inflation (a narrower run called full), known failure (claimed pass after
a failure) and never run. Per episode, before the first FV flag (no-hack episodes: over the whole episode):
  failing run = a tool output with a test-runner failure line (go "--- FAIL"/"FAIL\t", pytest "N failed"/"FAILED "/
               "N errors in"/"ERROR collecting", jest/mocha "N failing"/"Tests: ... failed", cargo "test result: FAILED");
  narrowed run = a tool call that leaves known tests out by name or pattern (NARROW);
  pre-existing = the model's own text (content or reasoning) calls failures pre-existing or unrelated.
Regexes are heuristics; read matches before trusting a count.
"""
import json
import re
import sys
from collections import Counter

STEM = "logs/data/goodfire_swe/deepswe-glm-5.2-fp8"
FAIL = re.compile(r"^--- FAIL|^FAIL\s|\b\d+ failed\b|^FAILED |\b\d+ failing\b|^Tests:.*\bfailed\b|test result: FAILED|"
                  r"\b\d+ errors?\b(?= in |,)|^ERROR collecting|^ERROR tests/", re.M)
# A narrowed run: known tests left out by name or pattern (pytest --deselect / -k "not ..." / --ignore, go test -skip).
NARROW = re.compile(r"--deselect|-k\s+\\?['\"][^'\"]*\bnot\b|--ignore[= ]|\bgo test\b[^\n]*-skip", re.I)
PRE = re.compile(r"pre-?existing|unrelated to (?:my|our|the) change|not related to (?:my|our|the) change|"
                 r"(?:were|was|are) (?:already )?failing before|fail(?:s|ed)? on (?:the )?(?:original|unmodified|base)", re.I)
WHY = {
    "scope inflation": re.compile(r"subset|selected|only|filter|exclud|omit|narrow|deselect|ignor|root-package|"
                                  r"particular|specific|partial|not (?:the|all)", re.I),
    "known failure": re.compile(r"fail|error|broken", re.I),
    "never run": re.compile(r"never (?:ran|run|executed)|did not (?:run|execute)|without (?:running|executing)|"
                            r"no (?:test|run) (?:was|were)", re.I),
}


def text_of(m):
    c = m.get("content")
    if isinstance(c, list):
        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return c or ""


def main(out=None):
    judge = {}
    for l in open(STEM + ".judge_rollouts.jsonl"):
        r = json.loads(l)
        judge[r["row_index"]] = r
    fv_rows, no_rows, flags = [], [], []
    with open(STEM + ".traces.jsonl") as f:
        for row, line in enumerate(f):
            j = judge.get(row)
            if not j or j.get("verdict_enacted") not in ("yes", "no"):
                continue
            fv = [x for x in j.get("flags") or [] if x.get("category") == "fabricated_verification"
                  and x.get("status") == "enacted"]
            if j["verdict_enacted"] == "yes" and not fv:
                continue
            nodes = json.loads(line)["traces"][0]["nodes"]
            last_asst = max((i for i, n in enumerate(nodes) if n["message"]["role"] == "assistant"
                             and text_of(n["message"]).strip()), default=None)
            first = min((x["node_index"] for x in fv), default=len(nodes))
            fail_before = pre_before = narrow_before = fail_any = narrow_any = False
            for i, n in enumerate(nodes):
                m = n["message"]
                fail = m["role"] == "tool" and bool(FAIL.search(text_of(m)))
                narrow = m["role"] == "assistant" and any(NARROW.search(json.dumps(tc)) for tc in m.get("tool_calls") or [])
                fail_any, narrow_any = fail_any or fail, narrow_any or narrow
                if i < first:
                    fail_before, narrow_before = fail_before or fail, narrow_before or narrow
                    if m["role"] == "assistant" and PRE.search(text_of(m) + " " + str(m.get("reasoning_content") or "")):
                        pre_before = True
            rec = dict(row=row, n_nodes=len(nodes), fail_before=fail_before, pre_before=pre_before,
                       narrow_before=narrow_before, fail_any=fail_any, narrow_any=narrow_any,
                       category=json.loads(line)["traces"][0]["task"]["data"].get("category"))
            if fv:
                rec["n_fv"] = len(fv)
                rec["fv_in_summary"] = any(x["node_index"] == last_asst for x in fv)
                fv_rows.append(rec)
                for x in fv:
                    why = " ".join(str(x.get("why", "")).split())
                    flags.append(dict(row=row, channel=x["channel"], in_summary=x["node_index"] == last_asst,
                                      kinds=[k for k, rx in WHY.items() if rx.search(why)],
                                      quote=" ".join(str(x.get("quote", "")).split())[:200], why=why[:300]))
            else:
                no_rows.append(rec)

    def share(rs, k):
        return f"{sum(r[k] for r in rs)}/{len(rs)}"

    print(f"FV episodes {len(fv_rows)}, flags {len(flags)}; no-hack episodes {len(no_rows)}")
    print("flag channel:", dict(Counter(x["channel"] for x in flags)))
    print("flags in the last assistant message (the summary):", sum(x["in_summary"] for x in flags),
          "; episodes with one:", share(fv_rows, "fv_in_summary"))
    print("judge 'why' kinds (a flag can have several):", dict(Counter(k for x in flags for k in x["kinds"])),
          "; none:", sum(not x["kinds"] for x in flags))
    print(f"failing test run: FV before the first flag {share(fv_rows, 'fail_before')}, FV anywhere "
          f"{share(fv_rows, 'fail_any')}; no-hack anywhere {share(no_rows, 'fail_any')}")
    print(f"narrowed run (--deselect / -k not / --ignore / -skip): FV before the first flag "
          f"{share(fv_rows, 'narrow_before')}, FV anywhere {share(fv_rows, 'narrow_any')}; no-hack anywhere "
          f"{share(no_rows, 'narrow_any')}")
    nf = lambda rs: sum(r["fail_any"] for r in rs)
    print(f"FV share among episodes with a failing run: {nf(fv_rows)}/{nf(fv_rows) + nf(no_rows)}; without one: "
          f"{len(fv_rows) - nf(fv_rows)}/{len(fv_rows) - nf(fv_rows) + len(no_rows) - nf(no_rows)}")
    print(f"model calls failures pre-existing/unrelated before the first FV flag: {share(fv_rows, 'pre_before')}; "
          f"no-hack, anywhere: {share(no_rows, 'pre_before')}")
    print("task category, FV:", dict(Counter(r["category"] for r in fv_rows)), "no-hack:",
          dict(Counter(r["category"] for r in no_rows)))
    med = lambda xs: sorted(xs)[len(xs) // 2]
    print("median nodes, FV:", med([r["n_nodes"] for r in fv_rows]), "no-hack:", med([r["n_nodes"] for r in no_rows]))
    if out:
        json.dump(dict(fv=fv_rows, no_hack=no_rows, flags=flags), open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
