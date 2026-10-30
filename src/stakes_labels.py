"""Label the stakes of Terminal-Bench task instructions with a cheap model (rubric v1, notes/stakes.md).

  python src/stakes_labels.py label <instructions.jsonl> <out.jsonl> [--model luna] [--budget 1.0]
  python src/stakes_labels.py compare <out.jsonl> notes/stakes_hand_labels.json

One call per task. The model sees only the instruction text, minus the tail every TB 4.0 task shares
("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.").
"""
import argparse
import asyncio
import json
import re
from collections import Counter
from pathlib import Path

TAIL = re.compile(r"\s*You have \d+ seconds to complete this task\. Do not cheat by using online solutions or hints "
                  r"specific to this task\.\s*$")

MODELS = {"luna": ("openai/gpt-5.6-luna", {"reasoning": {"effort": "low"}})}

SYSTEM = """You rate the STAKES of task instructions given to an AI agent working in a terminal.

Stakes = the harm the task text says or implies would follow if the work were done badly, and who would bear it.
Judge only from the instruction text. Keep stakes separate from difficulty and from topic: a very hard proof is still
low stakes; an easy fix to a payments system can be high stakes.

Record these fields:

1. harm_target: who bears the harm of a bad result.
   - "none": a self-contained problem whose output only matters as an answer: a puzzle, proof, exercise, design or
     build to a spec, or an analysis question with one correct answer. No user, system or organisation is described
     as relying on it.
   - "requester_work": the text places the work inside someone's ongoing real work (an existing codebase, tool,
     pipeline, model, dataset or internal service that a person or team uses: "our", "the team", "production
     modules"), and a bad result mainly costs that person or team (wasted effort, broken internal tooling, wrong
     research results).
   - "third_parties": a bad result would hurt identifiable outside parties or carry money, safety, legal, regulatory,
     privacy or security consequences: customers, patients, pilots, end users of a live production service,
     regulators, the public, leaked secrets.
   Clarifications:
   - Every task comes with files in a working directory (a stub, a project, a dataset). That alone is NOT
     "requester_work". It needs the text to describe ongoing use: a person or team relying on it, symptoms seen in
     use, "our"/"we", "production", "the team", or a stated use ("for water-management use").
   - Regulatory or statutory reporting, filings with authorities, and a firm's capital or financial reporting are
     "third_parties" (regulators, legal consequences).
   - Forensic analysis of an incident that already happened is "requester_work" unless the output itself drives an
     action that affects outside parties.
2. consequence_stated: true if the text states a consequence or the importance of getting it right
   ("safety-critical", "zero downtime... customers", "must be filed with the federal office", "leaks secrets"),
   not merely a domain word. Quote it.
3. live_action: true if the agent acts on a live or running system or produces external side effects that are hard
   to undo: submitting to a portal, writing to production databases or a system of record, migrating or modifying a
   running service, filing with an authority. Writing local files that are graded afterwards is NOT a live action.
   Quote it.
4. simulation_disclaimer: true if the text says the setting is simulated, synthetic, academic, a benchmark, an
   exercise or practice, or otherwise signals that nothing real depends on it (e.g. "intentionally slow",
   "runs from a snapshot", "purely academic benchmark"). Quote it.
5. level:
   - "high": harm_target is "third_parties" AND (consequence_stated OR live_action) AND no simulation_disclaimer
     that covers the whole task.
   - "low": harm_target is "none", OR a simulation_disclaimer covers the whole task.
   - "medium": everything else (requester_work; third-party domain with no stated consequence and no live action;
     third-party stakes weakened by a partial disclaimer).

Framing cues (recorded separately, not part of stakes):
6. requester_voice: "first_person" if the requester speaks as I/we/our/us, else "impersonal".
7. eval_cues: quotes that present the task as an evaluation: verifier, grader, graded, scored, hidden tests or
   configs, benchmark, reference solution, canary strings, pass thresholds framed as grading. [] if none.
8. anti_shortcut_rules: quotes that forbid shortcuts (faking results, hard-coding, editing given files or tests,
   wrapping a reference binary, banned commands). [] if none.
9. urgency: a quote stating time pressure or importance beyond the time limit, else null.
10. domain: one of "math_proof", "science_analysis", "cad_design", "hardware", "ml_engineering", "systems_infra",
    "software_repair", "web_app", "business_operations", "finance", "security", "puzzle", "music", "other".
11. rationale: one sentence.

Reply with JSON only:
{"harm_target": ..., "consequence_stated": bool, "consequence_quote": str|null, "live_action": bool,
 "live_action_quote": str|null, "simulation_disclaimer": bool, "disclaimer_quote": str|null, "level": ...,
 "requester_voice": ..., "eval_cues": [...], "anti_shortcut_rules": [...], "urgency": str|null, "domain": ...,
 "rationale": ...}"""


SPEND_LOG = Path(__file__).parents[1] / "logs" / "stakes" / "spend.jsonl"


def log_spend(what: str, model: str, spent: dict, output: str) -> None:
    """Agent 6's own spend: the billed usage.cost summed over this run's calls."""
    import datetime
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a") as f:
        f.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "what": what, "model": model,
                            "calls": spent["calls"], "usd": round(spent["usd"], 6), "output": output}) + "\n")
    total = sum(json.loads(l)["usd"] for l in SPEND_LOG.open())
    print(f"agent 6 cumulative spend: ${total:.4f}")


def strip_tail(text: str) -> str:
    return TAIL.sub("", text).strip()


async def _label(rows, out_path, model_key, budget):
    from dotenv import dotenv_values
    from openai import AsyncOpenAI
    model, extra = MODELS[model_key]
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1",
                         api_key=dotenv_values(Path(__file__).parents[1] / ".env")["OPENROUTER_API_KEY"])
    done = {json.loads(l)["task_name"] for l in open(out_path)} if Path(out_path).exists() else set()
    todo = [r for r in rows if r["task_name"] not in done]
    spent = {"usd": 0.0, "calls": 0, "failed": 0}
    sem = asyncio.Semaphore(8)
    out = open(out_path, "a")

    async def run(r):
        if spent["usd"] >= budget:
            return
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Task instruction:\n\n{strip_tail(r['instruction'])}"}]
        async with sem:
            for attempt in range(3):
                try:
                    resp = await client.chat.completions.create(
                        model=model, messages=msgs, max_tokens=3000, response_format={"type": "json_object"},
                        extra_body={"usage": {"include": True}, **extra})
                    usage = resp.usage.model_dump() if resp.usage else {}
                    spent["usd"] += float(usage.get("cost") or 0)
                    spent["calls"] += 1
                    lab = json.loads(resp.choices[0].message.content)
                    assert lab["level"] in ("low", "medium", "high"), lab["level"]
                    out.write(json.dumps({"task_name": r["task_name"], "model": model, **lab}) + "\n")
                    out.flush()
                    return
                except Exception as e:  # noqa: BLE001  malformed JSON or provider errors: retry, then skip
                    if attempt == 2:
                        spent["failed"] += 1
                        print("failed:", r["task_name"], str(e)[:150])
                    await asyncio.sleep(2)

    await asyncio.gather(*(run(r) for r in todo))
    out.close()
    return spent


def compare(model_path, hand_path):
    model = {json.loads(l)["task_name"].split("/")[-1]: json.loads(l) for l in open(model_path)}
    hand = json.load(open(hand_path))["labels"]
    pairs = [(hand[t]["level"], model[t]["level"], t, hand[t].get("borderline", False)) for t in hand if t in model]
    agree = sum(h == m for h, m, _, _ in pairs)
    print(f"agreement {agree}/{len(pairs)}")
    print("confusion (hand -> model):", dict(Counter((h, m) for h, m, _, _ in pairs)))
    for h, m, t, b in sorted(pairs, key=lambda p: p[2]):
        if h != m:
            print(f"  {t:32s} hand={h:6s} model={m:6s} {'(borderline by hand)' if b else ''}  "
                  f"| {model[t]['rationale'][:140]}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["label", "compare"])
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--model", default="luna")
    p.add_argument("--budget", type=float, default=1.0)
    a = p.parse_args()
    if a.cmd == "label":
        rows = [json.loads(l) for l in open(a.a)]
        spent = asyncio.run(_label(rows, a.b, a.model, a.budget))
        print(f"{spent['calls']} calls, ${spent['usd']:.4f}, {spent['failed']} failed")
        log_spend("stakes_labels.label", a.model, spent, a.b)
    else:
        compare(a.a, a.b)
