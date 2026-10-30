"""S24: a fresh held-out dev split, ``val2`` (card S24 in mu-log; studies/S24.md).

Items authored by Sonnet subagents from jle's briefs (``jle/notes/x90-briefs``) with an avoid list of every target used
by the bench, fit, val and jle's banks v2 / v3 (``data/dev/val2-authoring/<family>-avoid.json``; targets only, no
bench prompts), into ``data/dev/val2-authoring/raw/<family>-*.jsonl``. Three stages, each a mechanical rule stated
before any read (no centre and no lens is used to pick items):

  filter (Mac, tokenizer only): jle's x90 filters (schema, duplicate, bench overlap, multiword, leak, single-token
    reachability; ``x90_devbank.filter_family``), then S24's: drop an item whose accepted forms meet any target of the
    bench, fit, val, v2, v3 (``seen_target``) or of an earlier kept val2 item of any family (``shared_target``).
    -> ``data/dev/val2-authoring/filtered/<family>.jsonl`` + ``report.json``
  gate (GPU, the 27B): jle's capability gate unchanged (the bench's instruction, 1 greedy + 10 draws at T 0.7, strict
    string grader, pass = greedy right and >= 0.8 of the draws). -> ``data/dev/val2-authoring/gate-qwen27b.json``
  freeze (CPU): gate-passing items -> ``data/dev/<family>/val2.json`` in the bench's items.json format (multihop gets
    the bench's last-word readout), all of them (no subsampling).

  python experiments/s24_build.py filter
  python experiments/s24_build.py gate --device cuda          # on a capture pod
  python experiments/s24_build.py freeze
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from jlm import REPO_ROOT
from jlm.banks import DEV_ROOT

JLE = REPO_ROOT.parent / "jlens-edits-1"  # jle's own checkout, next to this repo
sys.path.insert(0, str(JLE / "experiments"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import x90_devbank as dv  # noqa: E402
import x90_gate as gt  # noqa: E402

MODEL = "Qwen/Qwen3.6-27B"
#: val2 (S24): every target fresh. val2b (S24b): multihop's closed-answer subfamilies and multilingual, under jle's rule
#: (a new prompt / subject; the answer may repeat a bank's), except multihop element_material, which stays strict.
SETS = {
    "val2": {"families": ("typo", "association", "multihop"), "relaxed": lambda fam, it: False},
    "val2b": {"families": ("multihop", "multilingual"),
              "relaxed": lambda fam, it: not (fam == "multihop" and it.get("subfamily") == "element_material")},
    "val3": {"families": ("typo", "association", "multihop"), "relaxed": lambda fam, it: False},
}
FAMILIES = SETS["val2"]["families"]
AUTH = DEV_ROOT / "val2-authoring"
SPLIT = "val2"


def use_set(name: str) -> None:
    global FAMILIES, AUTH, SPLIT
    FAMILIES, AUTH, SPLIT = SETS[name]["families"], DEV_ROOT / f"{name}-authoring", name


def seen_prompts(fam: str) -> set[str]:
    """Normalised prompts of fit, val, val2 and jle's banks v2 / v3 (the relaxed rule: the prompt must be new)."""
    from jlm import banks

    norm = lambda t: " ".join(str(t).split()).casefold()  # noqa: E731
    out = set()
    for split in ("fit", "val", "val2", "val2b"):
        try:
            out |= {norm(it.get("prompt", "")) for it in banks.load(fam, split).items}
        except FileNotFoundError:
            pass
    for v in ("bank-v2", "bank-v3"):
        out |= {norm(r.get("prompt", "")) for r in dv.read_jsonl(JLE / "data" / "x90-dev" / v / f"{fam}.jsonl")}
    return out


def stage_filter() -> None:
    from transformers import AutoTokenizer
    from umot.provenance import PINS

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    ex = json.loads(dv.EXCLUSIONS.read_text())
    pairs = dv.bench_pairs()
    (AUTH / "filtered").mkdir(parents=True, exist_ok=True)
    used: set[str] = set()  # accepted forms of kept val2 items, across families
    report = {}
    for fam in FAMILIES:
        raw = [r for p in sorted((AUTH / "raw").glob(f"{fam}-*.jsonl")) for r in dv.read_jsonl(p)]
        avoid = {dv.normalise(w) for w in json.loads((AUTH / f"{fam}-avoid.json").read_text())}
        # jle's schema check wants dev-<code>-<packet>-NNN names; check under that form, keep our v2- names
        for r in raw:
            r["_v2name"], r["name"] = r["name"], re.sub(r"^v\d+-", "dev-", r["name"])
        kept, drops = dv.filter_family(fam, raw, {}, ex, pairs, tok)
        back = {r["name"]: r["_v2name"] for r in raw}
        for d in drops:
            d["name"] = back.get(d["name"], d["name"])
        kept = [{**{k: v for k, v in it.items() if k != "_v2name"}, "name": back[it["name"]]} for it in kept]
        final = []
        prompts = seen_prompts(fam)
        relaxed = SETS[SPLIT]["relaxed"]
        for it in kept:
            acc = set(dv.accepted(it))
            if SPLIT == "val3":  # A's audit of val3: the final answer counts too (multihop's target, not only its bridge)
                acc |= {dv.normalise(str(it["target"]))} if it.get("target") else set()
                acc |= {w[:-1] for w in acc if w.endswith("s")} | {w + "s" for w in acc}  # plural variants (lungs ~ lung)
            pn = " ".join(it["prompt"].split()).casefold().rstrip(' "')
            near = next((q for q in prompts if len(pn.split()) >= 3 and (q.rstrip(' "').startswith(pn) or pn.startswith(q.rstrip(' "')) and len(q.split()) >= 3)), None)
            if near is not None:  # exact, or one prompt a word-prefix of the other (A's audit: "... es" vs "... es el")
                drops.append({"name": it["name"], "code": "seen_prompt", "reason": f"prompt of fit / val / val2 / v2 / v3: {near!r}"})
            elif relaxed(fam, it):  # jle's rule: the answer may repeat; record whether it is fresh
                final.append({**it, "source": f"S24 {SPLIT} (Sonnet-authored from jle x90 briefs)", "fresh_target": not (acc & avoid),
                              "fresh_answer": not ({dv.normalise(str(it.get("target", "")))} & avoid) if it.get("target") else not (acc & avoid)})
            elif acc & avoid:
                drops.append({"name": it["name"], "code": "seen_target", "reason": str(sorted(acc & avoid))})
            elif acc & used:
                drops.append({"name": it["name"], "code": "shared_target", "reason": str(sorted(acc & used))})
            else:
                used |= acc
                final.append({**it, "source": f"S24 {SPLIT} (Sonnet-authored from jle x90 briefs)", "fresh_target": True,
                              "fresh_answer": not ({dv.normalise(str(it.get("target", "")))} & avoid) if it.get("target") else True})
        path = AUTH / "filtered" / f"{fam}.jsonl"
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in final))
        codes: dict[str, int] = {}
        for d in drops:
            codes[d["code"]] = codes.get(d["code"], 0) + 1
        report[fam] = {"raw": len(raw), "kept": len(final), "dropped": codes, "drops": drops}
        print(f"{fam}: raw {len(raw)} -> kept {len(final)}; dropped {codes}")
    (AUTH / "filtered" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))


def stage_gate(device: str, limit: int | None) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from umot.provenance import PINS

    rev = PINS[MODEL]
    tok = AutoTokenizer.from_pretrained(MODEL, revision=rev)
    hf = AutoModelForCausalLM.from_pretrained(MODEL, revision=rev, dtype=torch.bfloat16, device_map=device).eval()
    rows = [(f, it) for f in FAMILIES for it in dv.read_jsonl(AUTH / "filtered" / f"{f}.jsonl")]
    if limit:
        rows = [r for f in FAMILIES for r in [x for x in rows if x[0] == f][:limit]]
    out = AUTH / "gate-qwen27b.json"
    result = {"provenance": {"experiment": "S24 val2 gate (jle x90_gate, unchanged settings)", "hub": MODEL, "revision": rev,
                             "draws": gt.DRAWS, "temperature": gt.TEMPERATURE, "threshold": gt.THRESHOLD,
                             "max_new_tokens": gt.MAX_NEW_TOKENS, "seed": gt.SEED, "limit": limit}, "items": {}}
    t0 = time.time()
    for n, (fam, it) in enumerate(rows):
        messages = [{"role": "system", "content": gt.ANSWER_SYSTEM}, {"role": "user", "content": gt.ask_of(fam, it)}]
        ids = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=False, return_tensors="pt")
        ids = (ids["input_ids"] if hasattr(ids, "keys") else ids).to(hf.device)
        mask = torch.ones_like(ids)
        torch.manual_seed(gt.SEED + n)
        with torch.no_grad():
            g = hf.generate(ids, attention_mask=mask, max_new_tokens=gt.MAX_NEW_TOKENS, do_sample=False, pad_token_id=tok.eos_token_id)
            s = hf.generate(ids, attention_mask=mask, max_new_tokens=gt.MAX_NEW_TOKENS, do_sample=True, temperature=gt.TEMPERATURE,
                            top_p=1.0, top_k=0, num_return_sequences=gt.DRAWS, pad_token_id=tok.eos_token_id)
        dec = lambda row: tok.decode(row[ids.shape[1]:], skip_special_tokens=True).strip()  # noqa: E731
        greedy, sampled = dec(g[0]), [dec(r) for r in s]
        golds = gt.golds_of(fam, it)
        result["items"][it["name"]] = {"family": fam, "golds": golds, "greedy": greedy, "sampled": sampled,
                                       **gt.verdict(gt.grade(greedy, golds), [gt.grade(a, golds) for a in sampled])}
        if (n + 1) % 25 == 0 or n + 1 == len(rows):
            done = result["items"].values()
            print(f"[gate {time.time() - t0:6.0f}s] {n + 1}/{len(rows)} pass {sum(v['pass'] for v in done)}", flush=True)
            tmp = out.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1))
            tmp.rename(out)
    result["summary"] = {f: {"n": sum(v["family"] == f for v in result["items"].values()),
                             "pass": sum(v["pass"] for v in result["items"].values() if v["family"] == f)} for f in FAMILIES}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(json.dumps(result["summary"]))


def stage_freeze() -> None:
    from transformers import AutoTokenizer
    from umot.provenance import PINS

    from import_jle_dev import last_word_readout

    gate = json.loads((AUTH / "gate-qwen27b.json").read_text())
    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    for fam in FAMILIES:
        rows = [it for it in dv.read_jsonl(AUTH / "filtered" / f"{fam}.jsonl") if gate["items"].get(it["name"], {}).get("pass")]
        items = []
        for it in rows:
            it = {**it, "family": fam, "split": SPLIT, "target_in_bench": False,
                  "consistency": gate["items"][it["name"]]["consistency"], "verified": False}
            if fam == "multihop":
                it["readout"] = last_word_readout(it["prompt"], tok)
            items.append(it)
        header = {"family": fam, "split": SPLIT, "source": f"S24 {SPLIT}: Sonnet-authored from jle x90 briefs, filtered, 27B-gated",
                  "gate": gate["provenance"], "dropped_target_in_bench": 0}
        path = DEV_ROOT / fam / f"{SPLIT}.json"
        path.write_text(json.dumps({**header, "items": items}, ensure_ascii=False, indent=1) + "\n")
        print(f"{fam}/{SPLIT}: {len(items)} items -> {path}")


def stage_rebuild() -> None:
    """Recover data/dev/<family>/<split>.json from the read-cell captures when the frozen files were lost with their pod
    (val3, 2026-10-12): the filtered items whose ids the capture holds, in capture order (the freeze's order). The
    per-item gate results (consistency) are lost and recorded as None."""
    import torch
    from transformers import AutoTokenizer
    from umot.provenance import PINS

    from import_jle_dev import last_word_readout
    from jlm import OUT

    tok = AutoTokenizer.from_pretrained(MODEL, revision=PINS[MODEL])
    for fam in FAMILIES:
        caps = torch.load(OUT / "captures" / f"{fam}-{SPLIT}.pt", weights_only=False)
        order = [c.id if hasattr(c, "id") else c["id"] for c in caps]
        rows = {it["name"]: it for it in dv.read_jsonl(AUTH / "filtered" / f"{fam}.jsonl")}
        items = []
        for iid in order:
            it = {**rows[iid], "family": fam, "split": SPLIT, "target_in_bench": False, "consistency": None, "verified": False}
            if fam == "multihop":
                it["readout"] = last_word_readout(it["prompt"], tok)
            items.append(it)
        header = {"family": fam, "split": SPLIT, "source": f"S24 {SPLIT}: Sonnet-authored from jle x90 briefs, filtered, 27B-gated",
                  "gate": {"note": "rebuilt from the read-cell captures (the pass set); per-item gate results lost with the pod",
                           "draws": gt.DRAWS, "temperature": gt.TEMPERATURE, "threshold": gt.THRESHOLD},
                  "dropped_target_in_bench": 0}
        path = DEV_ROOT / fam / f"{SPLIT}.json"
        path.write_text(json.dumps({**header, "items": items}, ensure_ascii=False, indent=1) + "\n")
        print(f"{fam}/{SPLIT}: {len(items)} items rebuilt -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("stage", choices=["filter", "gate", "freeze", "rebuild"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--set", default="val2", choices=tuple(SETS))
    args = ap.parse_args()
    use_set(args.set)
    {"filter": stage_filter, "gate": lambda: stage_gate(args.device, args.limit), "freeze": stage_freeze,
     "rebuild": stage_rebuild}[args.stage]()


if __name__ == "__main__":
    main()
