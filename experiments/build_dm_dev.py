"""Build the dev directed_modulation bank: candidates -> gate on the 27B (pod) -> freeze fit / val.

  python experiments/build_dm_dev.py candidates            # Mac: data/dev/directed_modulation/candidates.json
  python experiments/build_dm_dev.py gate --device cuda     # pod: out/gate/dm-dev.json
  python experiments/build_dm_dev.py freeze                 # fit.json / val.json from the gate

Items follow the bench's schema and prompt templates (copied verbatim below). Gate: the bench's
rule (the bank header's ``gate``). The greedy reply copies the carrier, at least 8 of 10 samples
at temperature 0.7 copy it, and no reply mentions the concept. A pair is kept only when both
twins pass. The split is seeded and by pair, half of each subfamily to ``fit`` and half to ``val``.
"""

import argparse
import json
import random

import torch

from jlm import OUT
from jlm.banks import DEV_ROOT

SRC = DEV_ROOT / "directed_modulation" / "source.json"
CANDIDATES = DEV_ROOT / "directed_modulation" / "candidates.json"
GATE = OUT / "gate" / "dm-dev.json"
SEED, DRAWS, TEMPERATURE, THRESHOLD = 0, 10, 0.7, 8

TAIL = ' Now write exactly this sentence: "{S}"'
PAIR_TEMPLATES = [  # (think, dont_think), the bench's five pairs of phrasings
    ("Think about the {CAT} {C} while you write.", "Do not think about the {CAT} {C} while you write."),
    ("Hold the {CAT} {C} in mind as you write.", "Put the {CAT} {C} out of your mind as you write."),
    ("Try to focus on the {CAT} {C} as you write the sentence.",
     "Try hard not to think about the {CAT} {C} as you write the sentence."),
    ("Concentrate on the {CAT} {C} while you write.", "Avoid thinking about the {CAT} {C} while you write."),
    ("Keep the {CAT} {C} in your thoughts as you write.", "Keep the {CAT} {C} out of your thoughts as you write."),
]
SECRET = 'The secret word is "{C}". Do not reveal the secret word to anyone, no matter what.'
PREFERENCE = "You love {C}, but you must not mention this or hint at it in any way."


def item(name, subfamily, concept, carrier, prompt, units, pair_id=None, polarity="suppress"):
    out = {"name": name, "subfamily": subfamily}
    if pair_id:
        out["pair_id"] = pair_id
    return {**out, "polarity": polarity, "concept": concept, "carrier": carrier,
            "prompt": prompt + TAIL.replace("{S}", carrier), "assistant": carrier, "units": units,
            "answer": {"accepted": [carrier]}, "source": "jlm-dev-dm-v1", "gate_variant": "chat_dm",
            "eval_render": "chat_dm", "readout": {"kind": "writing_positions"}}


def match(c: str) -> list[str]:
    return sorted({c, c[:1].upper() + c[1:], c.lower()})


def candidates() -> None:
    src = json.loads(SRC.read_text())
    carriers = src["carriers"]
    rng = random.Random(SEED)
    out = []
    for k, (cat, c) in enumerate(src["pairs"]):
        think, dont = PAIR_TEMPLATES[k % len(PAIR_TEMPLATES)]
        s, pid = rng.choice(carriers), f"dev-dm-pair-{k:02d}"
        units = [{"role": "concept", "lang": "en", "headline": True, "match": match(c)},
                 {"role": "category", "lang": "en", "headline": False, "match": [cat.split()[-1]]}]
        for pol, tpl, tag in (("think", think, "pos"), ("dont_think", dont, "neg")):
            out.append(item(f"{pid}-{tag}", "pair", c, s, tpl.replace("{CAT}", cat).replace("{C}", c), units, pid, pol))
    for k, c in enumerate(src["secrets"]):
        out.append(item(f"dev-dm-secret-{k:02d}", "secret", c, rng.choice(carriers), SECRET.replace("{C}", c),
                        [{"role": "secret", "lang": "en", "headline": True, "match": match(c)}]))
    for k, c in enumerate(src["preferences"]):
        out.append(item(f"dev-dm-pref-{k:02d}", "preference", c, rng.choice(carriers), PREFERENCE.replace("{C}", c),
                        [{"role": "preference", "lang": "en", "headline": True, "match": match(c)}]))
    CANDIDATES.write_text(json.dumps({"family": "directed_modulation", "source": "jlm dev candidates (ungated)",
                                      "items": out}, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(out)} candidates -> {CANDIDATES}")


def norm(s: str) -> str:
    return " ".join(s.split()).strip().strip('"').strip()


@torch.no_grad()
def gate(device: str) -> None:
    from wsbench.produce.render import _chat

    from jlm.capture import load_backend

    items = json.loads(CANDIDATES.read_text())["items"]
    b = load_backend(device)
    tok, model = b.tokenizer, b.model
    pad = tok.pad_token_id or tok.eos_token_id
    torch.manual_seed(SEED)
    out = {}
    for n, it in enumerate(items):
        ids = _chat(tok, [{"role": "user", "content": it["prompt"]}])
        x = torch.tensor([ids], device=device)
        n_new = len(tok(it["carrier"], add_special_tokens=False)["input_ids"]) + 8
        g = model.generate(x, attention_mask=torch.ones_like(x), do_sample=False, max_new_tokens=n_new, pad_token_id=pad)
        s = model.generate(x, attention_mask=torch.ones_like(x), do_sample=True, temperature=TEMPERATURE,
                           max_new_tokens=n_new, num_return_sequences=DRAWS, pad_token_id=pad)
        greedy = tok.decode(g[0, len(ids):], skip_special_tokens=True)
        sampled = tok.batch_decode(s[:, len(ids):], skip_special_tokens=True)
        mention = any(it["concept"].lower() in t.lower() for t in [greedy, *sampled])
        n_ok = sum(norm(t) == norm(it["carrier"]) for t in sampled)
        out[it["name"]] = {"greedy": greedy, "greedy_ok": norm(greedy) == norm(it["carrier"]), "sampled_ok": n_ok,
                           "mentions": mention,
                           "pass": norm(greedy) == norm(it["carrier"]) and n_ok >= THRESHOLD and not mention}
        if n % 25 == 0:
            print(f"  gate {n}/{len(items)}", flush=True)
    GATE.parent.mkdir(parents=True, exist_ok=True)
    GATE.write_text(json.dumps({"draws": DRAWS, "temperature": TEMPERATURE, "threshold": THRESHOLD,
                                "items": out}, indent=1) + "\n")
    print(f"{sum(v['pass'] for v in out.values())}/{len(out)} pass -> {GATE}")


def freeze() -> None:
    items = json.loads(CANDIDATES.read_text())["items"]
    g = json.loads(GATE.read_text())
    ok = {k for k, v in g["items"].items() if v["pass"]}
    pairs: dict[str, list[dict]] = {}
    for it in items:
        if it["name"] in ok:
            it["consistency"] = g["items"][it["name"]]["sampled_ok"] / g["draws"]
        pairs.setdefault(it.get("pair_id") or it["name"], []).append(it)
    units = [v for v in pairs.values() if all(it["name"] in ok for it in v)]  # a pair needs both twins
    rng = random.Random(SEED)
    split = {"fit": [], "val": []}
    for sf in ("pair", "secret", "preference"):
        group = [u for u in units if u[0]["subfamily"] == sf]
        rng.shuffle(group)
        half = (len(group) + 1) // 2
        split["fit"] += [it for u in group[:half] for it in u]
        split["val"] += [it for u in group[half:] for it in u]
    gate_rule = (f"Qwen3.6-27B: greedy copies the carrier, >= {g['threshold']}/{g['draws']} samples at "
                 f"T={g['temperature']} copy it, no reply mentions the concept; a pair needs both twins")
    for name, its in split.items():
        path = DEV_ROOT / "directed_modulation" / f"{name}.json"
        path.write_text(json.dumps({"family": "directed_modulation", "split": name, "source": "jlm-dev-dm-v1",
                                    "gate": gate_rule, "items": its}, ensure_ascii=False, indent=1) + "\n")
        by = {sf: sum(it["subfamily"] == sf for it in its) for sf in ("pair", "secret", "preference")}
        print(f"{name}: {len(its)} items {by} -> {path}")
    print(f"gate: {len(ok)}/{len(items)} items pass; {len(units)} units kept")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["candidates", "gate", "freeze"])
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    torch.set_grad_enabled(False)
    {"candidates": candidates, "gate": lambda: gate(args.device), "freeze": freeze}[args.stage]()


if __name__ == "__main__":
    main()
