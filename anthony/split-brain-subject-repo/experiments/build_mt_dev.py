"""Build dev banks for the multi-token families: validate -> answers (pod) -> grade -> freeze.

  python experiments/build_mt_dev.py validate --family typo_mt     # Mac: stamp, check, dedupe
  python experiments/build_mt_dev.py answers --family typo_mt      # pod: 27B answers the gate questions
  python experiments/build_mt_dev.py grade --family typo_mt        # Mac: Haiku grades distinct answers
  python experiments/build_mt_dev.py freeze --family typo_mt       # Mac: gate, split fit / val

Candidates (``data/dev/<family>/candidates-raw.jsonl``) are authored in the bench's item schema.
``validate`` stamps ``probe_token_lens`` as the bench does (Qwen3.6-27B token count per form, the
min over case variants x bare / leading space), requires the bench's own contract to accept every
item (``regex.scored_units``), drops items that share a form, target or prompt with the bench,
and writes ``candidates.json``. The gate is the bench's: its own question
(``wsbench.capable.questions``, so the CONTINUE / CORRECT_SPELLING asks and, for multihop_mt, every
bridge question) under its answering system prompt, the model's chat template with thinking off,
one greedy answer and 10 samples at T=0.7. Each distinct answer is graded with the bench's grading
prompt by the development judge (Haiku 5.5, unpinned). An item passes when the greedy answer is
correct and at least 8/10 samples are; a multihop item needs every bridge question to pass too.
"""

import argparse
import json
import random
from pathlib import Path

import torch

from jlm import OUT
from jlm.banks import DEV_ROOT, path_of
from jlm.judge import DEV_JUDGE
from jlm.lens import MODEL

DRAWS, TEMPERATURE, THRESHOLD, SEED = 10, 0.7, 0.8, 0
GATE = OUT / "gate"


ROUND = ""  # "" for the first authoring round, "-round2" etc. for top-ups (set by --round)


def raw_path(family: str) -> Path:
    return DEV_ROOT / family / f"candidates-raw{ROUND}.jsonl"


def cand_path(family: str, rnd: str | None = None) -> Path:
    return DEV_ROOT / family / f"candidates{ROUND if rnd is None else rnd}.json"


def rounds(family: str) -> list[str]:
    """Every authoring round of the family that has been gated (its gate file exists)."""
    out = []
    for p in sorted((DEV_ROOT / family).glob("candidates*.json")):
        rnd = p.stem.removeprefix("candidates")
        if (GATE / f"{family}{rnd}-gate.json").exists():
            out.append(rnd)
    return out


def tokenizer():
    from transformers import AutoTokenizer
    from umot.provenance import PINS

    return AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])


def count(tok, form: str) -> int:
    """The bench's strict count: min over case variants x bare / leading-space."""
    variants = {form, form.lower(), form[:1].upper() + form[1:], form.upper()}
    return min(len(tok(p + v, add_special_tokens=False)["input_ids"]) for v in variants for p in ("", " "))


def stamp(it: dict, tok) -> dict:
    units = {u["role"]: {lang: [count(tok, f) for f in forms] for lang, forms in (u.get("forms") or {}).items()}
             for u in it["units"]}
    out = {"units": units}
    if it.get("target"):
        out["target"] = count(tok, str(it["target"]))
    out["target_alts"] = [count(tok, str(a)) for a in it.get("target_alts") or []]  # the bench expects the key
    return out


def validate(family: str) -> None:
    from wsbench.banks import load_bank
    from wsbench.multitoken import regex

    tok = tokenizer()
    header, bench = load_bank(path_of(family, "bench"))
    contract = regex.contract_for(header, family)
    seen_bench = {str(x).lower() for it in bench for x in [it.get("target"), *(it.get("target_alts") or [])] if x}
    seen_bench |= {f.lower() for it in bench for u in it["units"] if u["role"] != "language"
                   for fs in (u.get("forms") or {}).values() for f in fs}
    bench_prompts = {it["prompt"].strip().lower() for it in bench}
    rows = [json.loads(line) for line in raw_path(family).read_text().splitlines() if line.strip()]
    kept, why = [], {}
    names, prompts = set(), set()
    for it in rows:
        it["probe_token_lens"] = stamp(it, tok)
        forms = {f.lower() for u in it["units"] if u["role"] != "language" for fs in (u.get("forms") or {}).values() for f in fs}
        targets = {str(x).lower() for x in [it.get("target"), *(it.get("target_alts") or [])] if x}
        reason = ""
        if it["name"] in names or it["prompt"].strip().lower() in prompts:
            reason = "duplicate"
        elif it["prompt"].strip().lower() in bench_prompts:
            reason = "bench prompt"
        elif (forms | targets) & seen_bench:
            reason = "shares a form or target with the bench"
        else:
            try:
                units = regex.scored_units(it, contract)
                if not any(u.required for u in units):
                    reason = "no required unit"
            except ValueError as e:
                reason = f"contract: {e}"[:120]
        if reason:
            why[it["name"]] = reason
            continue
        names.add(it["name"])
        prompts.add(it["prompt"].strip().lower())
        kept.append(it)
    head = {k: v for k, v in header.items() if k in ("family", "parent_family", "contract")}
    cand_path(family).write_text(json.dumps({**head, "source": "jlm-dev-mt-v1 (ungated)", "items": kept},
                                            ensure_ascii=False, indent=1) + "\n")
    print(f"{family}: {len(kept)}/{len(rows)} candidates kept -> {cand_path(family)}")
    for n, r in why.items():
        print(f"  dropped {n}: {r}")


def questions(family: str):
    """The bench's gate questions for our candidates (its builder, pointed at our items)."""
    from wsbench.banks import load_bank
    from wsbench.capable import questions as cq

    _h, items = load_bank(cand_path(family))
    orig = cq.bank_items
    cq.bank_items = lambda fam: items
    try:
        return cq.build(family)
    finally:
        cq.bank_items = orig


@torch.no_grad()
def answers(family: str, device: str) -> None:
    from wsbench.capable.run import ANSWER_SYSTEM
    from wsbench.produce.render import _chat

    from jlm.capture import load_backend

    qs = questions(family)
    b = load_backend(device)
    tok, model = b.tokenizer, b.model
    pad = tok.pad_token_id or tok.eos_token_id
    torch.manual_seed(SEED)
    out = {}
    for n, q in enumerate(qs):
        msgs = [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": q.ask}]
        ids = _chat(tok, msgs)  # the bench's chat render (thinking off), as a list of ids
        x = torch.tensor([ids], device=device)
        kw = {"attention_mask": torch.ones_like(x), "max_new_tokens": 40, "pad_token_id": pad}
        g = model.generate(x, do_sample=False, **kw)
        s = model.generate(x, do_sample=True, temperature=TEMPERATURE, num_return_sequences=DRAWS, **kw)
        n_in = len(ids)
        out[q.id] = {"greedy": tok.decode(g[0, n_in:], skip_special_tokens=True).strip(),
                     "samples": [tok.decode(t[n_in:], skip_special_tokens=True).strip() for t in s]}
        if n % 25 == 0:
            print(f"  answers {n}/{len(qs)}", flush=True)
    GATE.mkdir(parents=True, exist_ok=True)
    (GATE / f"{family}{ROUND}-answers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"{family}: {len(out)} questions answered -> {GATE / f'{family}{ROUND}-answers.json'}")


def grade(family: str) -> None:
    import hashlib
    import os

    from wsbench.cache import Cache
    from wsbench.capable.run import GRADE_SCHEMA, GRADE_SYSTEM, render_grade
    from wsbench.judge_config import JudgeConfig, resolve
    from wsbench.llm import Spend
    from wsbench.mcjudge import Call, Preflighter, run_calls

    from jlm.judge import _load_env, _patch_once

    _load_env()
    _patch_once()
    qs = {q.id: q for q in questions(family)}
    ans = json.loads((GATE / f"{family}{ROUND}-answers.json").read_text())
    key = lambda q, t: f"{family}|{q}|{hashlib.sha256(t.encode()).hexdigest()[:16]}"
    calls = {key(q, t): Call(key=key(q, t), system=GRADE_SYSTEM, user=render_grade(qs[q], t), meta={})
             for q, a in ans.items() for t in {a["greedy"], *a["samples"]} if t}
    judge = resolve(JudgeConfig(prompt_version="gate"), flag=DEV_JUDGE, env=os.environ)
    spend = Spend()
    with Cache(GATE / f"{family}{ROUND}-grades.jsonl") as cache:
        v = run_calls(list(calls.values()), schema=GRADE_SCHEMA, judge=judge, prompt_version="jlm-gate-v1",
                      cache=cache, spend=spend, concurrency=64, rpm=1200, dry_run=False,
                      preflight=Preflighter(False).for_judge(judge), temperature=0.0)
    ok = lambda q, t: bool(t) and isinstance(v.get(key(q, t)), dict) and v[key(q, t)]["correct"]
    rows = {q: {"greedy_ok": ok(q, a["greedy"]), "rate": sum(ok(q, t) for t in a["samples"]) / len(a["samples"])}
            for q, a in ans.items()}
    (GATE / f"{family}{ROUND}-gate.json").write_text(json.dumps({"judge": judge.model, "draws": DRAWS,
                                                          "temperature": TEMPERATURE, "threshold": THRESHOLD,
                                                          "questions": rows}, indent=1) + "\n")
    print(f"{family}: {len(calls)} distinct answers graded, spend ${spend.usd:.3f}")


def freeze(family: str) -> None:
    from wsbench.banks import load_bank

    header, items, g = None, [], {}
    for rnd in rounds(family):  # every gated round, merged before the split
        h, its = load_bank(cand_path(family, rnd))
        header = header or h
        items += its
        g |= json.loads((GATE / f"{family}{rnd}-gate.json").read_text())["questions"]
    passes = lambda q: q in g and g[q]["greedy_ok"] and g[q]["rate"] >= THRESHOLD
    kept = []
    for it in items:
        legs = [it["id"]] + [f"{it['id']}:bridge{n}" for n in range(1, len(it.get("bridges") or []) + 1)]
        if all(passes(q) for q in legs):
            it["consistency"] = g[it["id"]]["rate"]
            kept.append({k: v for k, v in it.items() if k != "id"})
    rng = random.Random(SEED)
    split = {"fit": [], "val": []}
    for sf in sorted({it.get("subfamily") for it in kept}, key=str):
        group = [it for it in kept if it.get("subfamily") == sf]
        rng.shuffle(group)
        half = (len(group) + 1) // 2
        split["fit"] += group[:half]
        split["val"] += group[half:]
    rule = (f"Qwen3.6-27B: the bench's gate question, greedy correct and >= {int(THRESHOLD * DRAWS)}/{DRAWS} at "
            f"T={TEMPERATURE}{', every bridge question too' if family == 'multihop_mt' else ''}; graded by "
            f"{DEV_JUDGE} with the bench's grading prompt")
    for name, its in split.items():
        path = DEV_ROOT / family / f"{name}.json"
        path.write_text(json.dumps({**{k: v for k, v in header.items()}, "split": name, "source": "jlm-dev-mt-v1",
                                    "gate": rule, "items": its}, ensure_ascii=False, indent=1) + "\n")
        print(f"{family}/{name}: {len(its)} items -> {path}")
    print(f"{family}: {len(kept)}/{len(items)} pass the gate")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["validate", "answers", "grade", "freeze"])
    ap.add_argument("--family", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--round", default="", help="authoring round suffix, pass as --round=-round2 (validate/answers/grade)")
    args = ap.parse_args()
    global ROUND
    ROUND = args.round
    torch.set_grad_enabled(False)
    for f in args.family.split(","):
        if args.stage == "answers":
            answers(f, args.device)
        else:
            {"validate": validate, "grade": grade, "freeze": freeze}[args.stage](f)


if __name__ == "__main__":
    main()
