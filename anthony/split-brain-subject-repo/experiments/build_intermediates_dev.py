"""Build dev banks for the hidden-intermediate families: candidates -> gate on the 27B (pod) -> freeze fit / val.

  python experiments/build_intermediates_dev.py candidates                 # Mac: data/dev/<family>/candidates.json
  python experiments/build_intermediates_dev.py gate --device cuda         # pod: out/gate/<family>-dev.json
  python experiments/build_intermediates_dev.py freeze                     # fit.json / val.json from the gate

Families: ``chain_intermediates`` and ``brew_intermediates``. Items follow the bench's schema and construction (the
prompt templates below are the bench's, verbatim), so ``wsbench.readplan`` reads them unchanged; the item names start
``dev-`` and no item repeats a bench item (chain: the same start and steps; brew: the same table and start).

chain: one to three dependent steps (add / subtract 2-9, double, triple, halve rounding down / up) on a start in 2-30,
depth 2 or 3 (70 / 30), every value in 1-99, start, intermediates and answer pairwise distinct, no intermediate a
numeral of the prompt. brew: a 10-row stir table over 10 of the bench's 12 colours (no self-loops), depth 2, start,
first stir and answer distinct; the 24 read cells and their regions are found in the chat render with the prefill
``Answer:`` exactly as the bench pins them (checked against every bench item in ``candidates``).

Gate (the bench's rule, seed-last prompts): greedy correct and 10 / 10 samples at T = 0.8, top-p 0.95 correct, max 16
new tokens, and (chain) no reply names an intermediate; brew suppresses end-of-turn after the prefill and checks the first colour word only. Freeze
splits the passers seeded, stratified by depth (chain), half to ``fit`` and half to ``val``. Freeze is deterministic
in the candidates and the gate file, so the pod's ``data/dev`` files can be rebuilt on the Mac from ``out/gate``.
"""

import argparse
import hashlib
import itertools
import json
import random
import re

import torch

from jlm import OUT
from jlm.banks import DEV_ROOT
from wsbench.registry import REPO_ROOT as WSBENCH_ROOT

FAMILIES = ("chain_intermediates", "brew_intermediates")
SEED, DRAWS, TEMPERATURE, TOP_P, MAX_NEW = 0, 10, 0.8, 0.95, 16
N_CANDIDATES = {"chain_intermediates": 520, "brew_intermediates": 720}
SOURCE = "jlm-dev-intermediates-v1"


def cand_path(family: str):
    return DEV_ROOT / family / "candidates.json"


def gate_path(family: str):
    return OUT / "gate" / f"{family}-dev.json"


def bench_items(family: str) -> list[dict]:
    return json.loads((WSBENCH_ROOT / "evals" / family / "items.json").read_text())["items"]


# ---------------------------------------------------------------- chain
CHAIN_HEAD = "Apply the steps below, in order, to the starting number given at the end."
CHAIN_TAIL = "The starting number is {S}. What is the final number? Reply with only the final number, nothing else."
CHAIN_HEAD_FIRST = "Start with the number {S} and apply the steps below, in order."
CHAIN_TAIL_FIRST = "What is the final number? Reply with only the final number, nothing else."
KINDS = ("add", "sub", "double", "triple", "halve_down", "halve_up")


def chain_step(kind: str, k: int | None) -> tuple[str, callable]:
    return {
        "add": (f"Add {k}.", lambda x: x + k),
        "sub": (f"Subtract {k}.", lambda x: x - k),
        "double": ("Double it.", lambda x: 2 * x),
        "triple": ("Multiply it by 3.", lambda x: 3 * x),
        "halve_down": ("Halve it, rounding down.", lambda x: x // 2),
        "halve_up": ("Halve it, rounding up.", lambda x: (x + 1) // 2),
    }[kind]


def chain_candidates(n: int, rng: random.Random) -> list[dict]:
    bench = {(it["start"], tuple(it["steps"])) for it in bench_items("chain_intermediates")}
    out, seen = [], set()
    while len(out) < n:
        depth = 3 if rng.random() < 0.3 else 2
        kinds = [rng.choice(KINDS) for _ in range(depth)]
        consts = [rng.randint(2, 9) if k in ("add", "sub") else None for k in kinds]
        start = rng.randint(2, 30)
        steps, vals, x = [], [], start
        for k, c in zip(kinds, consts):
            text, f = chain_step(k, c)
            steps.append(text)
            x = f(x)
            vals.append(x)
        inters, answer = vals[:-1], vals[-1]
        literals = sorted({start, *(c for c in consts if c is not None)})
        key = (start, tuple(steps))
        if (not all(1 <= v <= 99 for v in vals) or len({start, *vals}) != depth + 1
                or any(v in literals for v in inters) or key in bench or key in seen):
            continue
        seen.add(key)
        out.append({
            "depth": depth, "cond": False, "kinds": kinds, "steps": steps, "start": start, "intermediates": inters,
            "untaken": [None] * len(inters), "answer": answer,
            "prompt": "\n".join([CHAIN_HEAD, *steps, CHAIN_TAIL.format(S=start)]),
            "prompt_first": "\n".join([CHAIN_HEAD_FIRST.format(S=start), *steps, CHAIN_TAIL_FIRST]),
            "literals": literals, "name": f"dev-chain-d{depth}-{len(out):04d}", "source": SOURCE,
        })
    return out


# ---------------------------------------------------------------- brew
PALETTE = ("black", "blue", "brown", "gold", "gray", "green", "orange", "pink", "purple", "red", "teal", "white")
BREW_HEAD = ("Here is a colour-mixing problem. Answer with a single colour word and nothing else.\n"
             "Problem: A potion changes colour each time it is stirred, according to these rules:")
BREW_STIRS = "You stir the potion twice."
BREW_START = "The potion starts out {S}."
BREW_Q = "What colour is the potion at the end?"
PREFILL = "Answer:"


def article(c: str) -> str:
    return "An" if c[0] in "aeiou" else "A"


def brew_prompts(table: dict[str, str], start: str) -> tuple[str, str]:
    rules = [f"{article(c)} {c} potion turns {v} when stirred." for c, v in table.items()]
    last = "\n".join([BREW_HEAD, *rules, BREW_STIRS, BREW_START.format(S=start), BREW_Q])
    first = "\n".join([BREW_HEAD, *rules, BREW_START.format(S=start), BREW_STIRS, BREW_Q])
    return last, first


def brew_cells(tok, prompt: str) -> dict[str, str]:
    """{position: region} for the bench's 24 pinned cells, found in the chat render with the prefill."""
    from wsbench.produce.render import _chat, display_tokens

    t = display_tokens(tok, _chat(tok, [{"role": "user", "content": prompt}], PREFILL))

    def find(seq: list[str]) -> int:
        hits = [i for i in range(len(t) - len(seq) + 1) if t[i : i + len(seq)] == seq]
        if len(hits) != 1:
            raise RuntimeError(f"{seq}: {len(hits)} matches")
        return hits[0]

    s = find(["You", " stir", " the", " potion", " twice", "."])
    b = find(["The", " potion", " starts", " out"])
    q = find(["What", " colour", " is", " the", " potion", " at", " the", " end", "?"])
    a, th = find(["assistant"]), find(["</think>"])
    if t[-1] != ":" or t[a + 1] != "Ċ" or t[th + 1] != "ĊĊ":
        raise RuntimeError("unexpected render tail")
    cells = {**{p: "stir" for p in range(s, s + 6)}, **{p: "start" for p in range(b, b + 6)},
             **{p: "question" for p in range(q, q + 9)},
             a + 1: "emit_asst", th + 1: "emit_think", len(t) - 1: "emit_colon"}
    return {str(p): r for p, r in sorted(cells.items())}


def brew_candidates(n: int, rng: random.Random, tok) -> list[dict]:
    for it in bench_items("brew_intermediates"):  # the region finder must reproduce the bench's pins
        if brew_cells(tok, it["prompt"]) != it["regions"]:
            raise RuntimeError(f"{it['name']}: regions differ from the bench's")
    bench = {(json.dumps(it["table"], sort_keys=True), it["start"]) for it in bench_items("brew_intermediates")}
    out, seen = [], set()
    while len(out) < n:
        keys = rng.sample(PALETTE, 10)
        table = {c: rng.choice([d for d in keys if d != c]) for c in keys}
        start = rng.choice(keys)
        inter = table[start]
        answer = table[inter]
        key = (json.dumps({c: {"stir": v} for c, v in table.items()}, sort_keys=True), start)
        if len({start, inter, answer}) != 3 or key in bench or key in seen:
            continue
        seen.add(key)
        off = [c for c in keys if c not in (start, inter, answer)]
        adj = [inter, start, answer, *rng.sample(off, 2)]
        rnd = [inter, *rng.sample(off, 4)]
        rng.shuffle(adj)
        rng.shuffle(rnd)
        last, first = brew_prompts(table, start)
        regions = brew_cells(tok, last)
        out.append({
            "name": f"dev-brew-r10d2-{len(out):04d}", "mode": "single", "depth": 2, "n_rows": 10,
            "table": {c: {"stir": v} for c, v in table.items()}, "start": start, "stirs": ["stir", "stir"],
            "intermediates": [inter], "untaken": [], "answer": answer, "off_trajectory": off,
            "options_adjacent": [adj], "options_random": [rnd], "prompt_first": first, "prompt": last,
            "regions": regions, "eval_positions": [int(p) for p in regions], "source": SOURCE,
        })
    return out


# ---------------------------------------------------------------- stages
def candidates() -> None:
    from transformers import AutoTokenizer

    from jlm.lens import MODEL

    tok = AutoTokenizer.from_pretrained(MODEL)
    for family in FAMILIES:
        rng = random.Random(f"{SEED}-{family}")
        n = N_CANDIDATES[family]
        items = chain_candidates(n, rng) if family == "chain_intermediates" else brew_candidates(n, rng, tok)
        path = cand_path(family)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"family": family, "source": f"{SOURCE} candidates (ungated)", "items": items},
                                   ensure_ascii=False, indent=1) + "\n")
        print(f"{family}: {len(items)} candidates -> {path}")


def ints(s: str) -> list[int]:
    return [int(m) for m in re.findall(r"-?\d+", s)]


def words(s: str) -> list[str]:
    return re.findall(r"[a-z]+", s.lower())


def judge_reply(family: str, it: dict, text: str) -> tuple[bool, bool]:
    """(correct, names an intermediate) for one reply."""
    if family == "chain_intermediates":
        n = ints(text)
        return (bool(n) and n[0] == it["answer"]), any(v in n for v in it["intermediates"])
    # End-of-turn is suppressed after the prefill (the bench's gate), so the reply runs on past the answer and often
    # explains itself; only a colour named BEFORE the first colour word counts as a leak (none can be: the first colour
    # word is the answer or the reply is wrong), as in the bench, which rejected 0 / 400 for leaks.
    w = [x for x in words(text) if x in PALETTE]
    return (bool(w) and w[0] == it["answer"]), False


@torch.no_grad()
def gate(device: str, families: list[str], batch: int) -> None:
    from wsbench.produce.render import _chat

    from jlm.capture import load_backend

    b = load_backend(device)
    tok, model = b.tokenizer, b.model
    tok.padding_side = "left"
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    for family in families:
        items = json.loads(cand_path(family).read_text())["items"]
        prefill = PREFILL if family == "brew_intermediates" else ""
        kw = {"max_new_tokens": MAX_NEW, "pad_token_id": pad}
        if prefill:  # the bench's gate suppresses end-of-turn after the prefill
            kw["suppress_tokens"] = tok.convert_tokens_to_ids(["<|im_end|>", "<|endoftext|>"])
        torch.manual_seed(SEED)
        out = {}
        for k in range(0, len(items), batch):
            chunk = items[k : k + batch]
            seqs = [_chat(tok, [{"role": "user", "content": it["prompt"]}], prefill) for it in chunk]
            width = max(map(len, seqs))
            x = torch.tensor([[pad] * (width - len(s)) + s for s in seqs], device=device)
            m = torch.tensor([[0] * (width - len(s)) + [1] * len(s) for s in seqs], device=device)
            g = model.generate(x, attention_mask=m, do_sample=False, **kw)
            s = model.generate(x, attention_mask=m, do_sample=True, temperature=TEMPERATURE, top_p=TOP_P,
                               num_return_sequences=DRAWS, **kw)
            for j, it in enumerate(chunk):
                greedy = tok.decode(g[j, width:], skip_special_tokens=True)
                sampled = tok.batch_decode(s[j * DRAWS : (j + 1) * DRAWS, width:], skip_special_tokens=True)
                gok, gleak = judge_reply(family, it, greedy)
                res = [judge_reply(family, it, t) for t in sampled]
                n_ok = sum(c for c, _ in res)
                leak = gleak or any(lk for _, lk in res)
                out[it["name"]] = {"greedy": greedy, "greedy_ok": gok, "correct": n_ok, "n": DRAWS, "leaked": leak,
                                   "sampled": sampled, "pass": gok and n_ok == DRAWS and not leak}
            print(f"  {family} gate {min(k + batch, len(items))}/{len(items)}"
                  f" ({sum(v['pass'] for v in out.values())} pass)", flush=True)
        path = gate_path(family)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"family": family, "draws": DRAWS, "temperature": TEMPERATURE, "top_p": TOP_P,
                                    "max_new": MAX_NEW, "candidates_sha256": sha(cand_path(family)),
                                    "items": out}, indent=1) + "\n")
        print(f"{family}: {sum(v['pass'] for v in out.values())}/{len(out)} pass -> {path}")


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(families: list[str]) -> None:
    for family in families:
        items = json.loads(cand_path(family).read_text())["items"]
        g = json.loads(gate_path(family).read_text())
        if g["candidates_sha256"] != sha(cand_path(family)):
            raise RuntimeError(f"{family}: the gate was run on other candidates")
        ok = [dict(it, gate=g["items"][it["name"]] | {"sampled": None}) for it in items if g["items"][it["name"]]["pass"]]
        for it in ok:
            del it["gate"]["sampled"]
        rng = random.Random(f"{SEED}-{family}-split")
        split = {"fit": [], "val": []}
        for _, grp in itertools.groupby(sorted(ok, key=lambda it: it["depth"]), key=lambda it: it["depth"]):
            grp = list(grp)
            rng.shuffle(grp)
            half = (len(grp) + 1) // 2
            split["fit"] += grp[:half]
            split["val"] += grp[half:]
        rule = (f"Qwen3.6-27B, seed-last prompt{' with the prefill ' + repr(PREFILL) if family.startswith('brew') else ''}"
                f": greedy correct, {DRAWS}/{DRAWS} samples at T={TEMPERATURE}, top-p {TOP_P} correct, "
                f"no reply names an intermediate")
        for name, its in split.items():
            its.sort(key=lambda it: it["name"])
            path = DEV_ROOT / family / f"{name}.json"
            path.write_text(json.dumps({"family": family, "split": name, "source": SOURCE, "gate": rule,
                                        "n": len(its), "items": its}, ensure_ascii=False, indent=1) + "\n")
            depths = {d: sum(it["depth"] == d for it in its) for d in sorted({it["depth"] for it in its})}
            print(f"{family}/{name}: {len(its)} items, depths {depths} -> {path}")
        print(f"{family} gate: {len(ok)}/{len(items)} pass")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["candidates", "gate", "freeze"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--families", default=",".join(FAMILIES))
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    fams = args.families.split(",")
    {"candidates": candidates, "gate": lambda: gate(args.device, fams, args.batch),
     "freeze": lambda: freeze(fams)}[args.stage]()


if __name__ == "__main__":
    main()
