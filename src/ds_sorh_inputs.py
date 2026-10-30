"""Inputs for the DeepSeek-as-probe replication of her SoRH conclusions #1 and #4 (no API calls).

  .venv/bin/python src/ds_sorh_inputs.py first [<agent 1's texts.jsonl>]
      -> logs/sorh_ablation/ds_probe/first/input.jsonl

#1: the first message of B, G, r_student, r_student__c5_eval and r_student__c5_training on her 20 prompts, taken from
the files Qwen was probed on. Each text is checked against the first message actually sent to Qwen (answers.jsonl).
If agent 1's file is given (rows with prompt_id, cell, text), every text in it must equal ours byte for byte.

  .venv/bin/python src/ds_sorh_inputs.py switch <agent 3's switch_contexts.jsonl> [<out dir>]
      -> logs/sorh_ablation/ds_probe/switch/contexts.jsonl (+ an empty none_single.jsonl for the runner)

#4: agent 3's DeepSeek contexts, copied byte for byte after checks: roles user/assistant/user/assistant/user, no
system prompt, no reasoning tags, the two switch cells, unique (cell, prompt, sample). `--cells a,b` names other
allowed cells (e.g. the "Nobody will score" arm). `--pair <cue-10 contexts>` also checks that each row's first four
messages equal the same model's cue-10 "switched off" context for that (prompt, sample).

  .venv/bin/python src/ds_sorh_inputs.py anchor <family>      (glm, qwen27b)
      -> logs/eval_probe/p1_<family>_wildchat.jsonl

The WildChat anchor for another probe model (her GLM 5.2 / Qwen 27B replication): Qwen's 58 items
(p1_wildchat.jsonl), with only the family and item key changed, as DeepSeek's p1_ds_wildchat.jsonl was. Each chat is
checked equal to Qwen's and DeepSeek's. The same script serves #1 and #4 for those models (`first`, `switch <file>
<out dir>`).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "logs/sorh_ablation"
CELLS = ["B", "G", "r_student", "r_student__c5_eval", "r_student__c5_training"]
# (input file, answers file Qwen wrote) for each source of Qwen's reading
SOURCES = [(SA / "probe/cells_c0f2fe0.jsonl", SA / "probe/answers.jsonl"),
           (SA / "realness_candidates/input_realness_candidates.jsonl", SA / "realness_candidates/answers.jsonl"),
           (SA / "realness_candidates/step3/input_realness_cues_probe.jsonl",
            SA / "realness_candidates/step3/answers.jsonl")]


def rows(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def first():
    out, sent = {}, {}
    for inp, ans in SOURCES:
        for a in rows(ans):
            if a["cell"] in CELLS and a["probe"] == "purpose_mc":
                sent.setdefault((a["cell"], a["prompt_id"]), set()).add(a["prompt"][0]["content"])
        for r in rows(inp):
            if r["cell"] in CELLS:
                k = (r["cell"], r["prompt_id"])
                assert k not in out, f"{k} in two source files"
                out[k] = r["text"]
    for k, t in out.items():
        assert sent.get(k) == {t}, f"{k}: the text differs from what was sent to Qwen"
    n = Counter(c for c, _ in out)
    assert all(n[c] == 20 for c in CELLS), n
    assert len({p for _, p in out}) == 20, "not the same 20 prompts"
    lines = [json.dumps({"prompt_id": p, "cell": c, "text": out[(c, p)]}) + "\n"
             for c in CELLS for p in sorted(p for cc, p in out if cc == c)]
    d = SA / "ds_probe/first"
    d.mkdir(parents=True, exist_ok=True)
    body = "".join(lines)
    (d / "input.jsonl").write_text(body)
    print(f"{len(lines)} texts, {dict(n)}; each equals the first message sent to Qwen")
    print("input.jsonl sha256", hashlib.sha256(body.encode()).hexdigest())
    if len(sys.argv) > 2:
        theirs = {(r["cell"], r["prompt_id"]): r["text"] for r in rows(sys.argv[2]) if r["cell"] in CELLS}
        diff = [k for k in out if theirs.get(k) != out[k]]
        print(f"agent 1's file: {len(theirs)} of our {len(out)} texts present; {len(out) - len(diff)} identical; "
              f"differ or missing: {sorted(diff)[:10]}")


def switch():
    args = sys.argv[2:]
    cells = ("mt_cue10_off_switch", "mt_cue10_on_switch")
    if "--cells" in args:  # another arm's cell names, e.g. her "Nobody will score the task anymore." arm
        i = args.index("--cells")
        cells = tuple(args[i + 1].split(","))
        args[i:i + 2] = []
    pair = None
    if "--pair" in args:  # the same model's cue-10 contexts: each row's first four messages must equal its off twin's
        i = args.index("--pair")
        pair = {(r["prompt_id"], r.get("sample")): r["messages"][:4] for r in rows(args[i + 1])
                if r["cell"] == "mt_cue10_off_switch"}
        args[i:i + 2] = []
    src = Path(args[0])
    d = Path(args[1]) if len(args) > 1 else SA / "ds_probe/switch"
    b = src.read_bytes()
    rs = [json.loads(l) for l in b.decode().splitlines() if l.strip()]
    for r in rs:
        k = (r["cell"], r["prompt_id"], r.get("sample"))
        assert r["cell"] in cells, k
        assert not r.get("system_prompt"), f"{k}: a system prompt is set"
        assert [m["role"] for m in r["messages"]] == ["user", "assistant", "user", "assistant", "user"], k
        assert all(m["content"].strip() for m in r["messages"]), f"{k}: an empty message"
        assert not any(t in m["content"] for m in r["messages"] for t in ("<think>", "</think>")), f"{k}: reasoning"
    if pair is not None:
        bad = [(r["prompt_id"], r.get("sample")) for r in rs if pair.get((r["prompt_id"], r.get("sample"))) != r["messages"][:4]]
        assert not bad, f"first four messages differ from the cue-10 off twin: {bad[:5]}"
        print(f"paired: all {len(rs)} rows share their first four messages with the cue-10 off context")
    dup = [k for k, v in Counter((r["cell"], r["prompt_id"], r.get("sample")) for r in rs).items() if v > 1]
    assert not dup, f"duplicate (cell, prompt, sample): {dup[:3]}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "contexts.jsonl").write_bytes(b)
    (d / "none_single.jsonl").write_text("")
    print(f"{src}: sha256 {hashlib.sha256(b).hexdigest()}, {len(rs)} contexts")
    print("per (cell, prompt):", dict(sorted(Counter((r["cell"], r["prompt_id"]) for r in rs).items())))
    print("switch messages:", dict(Counter((r["cell"], r["messages"][-1]["content"][:60]) for r in rs)))
    print("->", d / "contexts.jsonl")


def anchor():
    fam = sys.argv[2]
    ep = ROOT / "logs/eval_probe"
    qwen, ds = rows(ep / "p1_wildchat.jsonl"), {r["id"]: r for r in rows(ep / "p1_ds_wildchat.jsonl")}
    assert len(qwen) == 58 and len(ds) == 58
    out = []
    for r in qwen:
        assert r["chat"] == ds[r["id"]]["chat"], f"{r['id']}: Qwen's and DeepSeek's chats differ"
        out.append({**r, "family": fam, "item": f"{r['item']}|{fam}",
                    "group": f"WildChat real users · {fam} probe"})
    body = "".join(json.dumps(r) + "\n" for r in out)
    p = ep / f"p1_{fam}_wildchat.jsonl"
    p.write_text(body)
    print(f"{len(out)} items, chats equal to Qwen's and DeepSeek's anchor -> {p.name}, sha256 "
          f"{hashlib.sha256(body.encode()).hexdigest()}")


def estimate():
    """estimate <new contexts.jsonl> <family> <cap> <old answers.jsonl>...: the switch probe's cost on new contexts.

    Per probe type (3 MC, 1 who-checks per context), from the same model's earlier switch answers:
      prompt tokens scale with the context's characters (chars per token measured on the old prompts);
      completion tokens stay at their old mean; the list price (eval_probe PRICE) is calibrated to the billed usd.
    Prints the expected cost, the ×1.5 high, and the cap the runner's checks need (first-cell start, before the last cell).
    """
    sys.path.insert(0, str(ROOT / "src"))
    import eval_probe as EP
    new, fam, cap, olds = Path(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5:]
    pin, pout = EP.PRICE[fam]
    old = [a for f in olds for a in rows(f) if a["cell"].startswith("mt_cue10") and a.get("prompt_tokens")]
    plan = {"purpose_mc": 3, "who_checks": 1}
    ctx_new = [sum(len(m["content"]) for m in r["messages"]) for r in rows(new)]
    cells = Counter(r["cell"] for r in rows(new))
    total = 0.0
    for probe, k in plan.items():
        a = [x for x in old if x["probe"] == probe]
        q = len(a[0]["prompt"][-1]["content"])  # the question's characters
        chars = sum(sum(len(m["content"]) for m in x["prompt"]) for x in a) / len(a)
        cpt = chars / (sum(x["prompt_tokens"] for x in a) / len(a))  # characters per prompt token
        ctok = sum(x["completion_tokens"] for x in a) / len(a)
        k_cal = (sum(x["usd"] for x in a) / len(a)) / ((chars / cpt) * pin / 1e6 + ctok * pout / 1e6)
        per = [k_cal * (((c + q) / cpt) * pin + ctok * pout) / 1e6 for c in ctx_new]
        total += k * sum(per)
        print(f"{probe}: old {len(a)} calls, {chars / cpt:.0f} prompt tok, {ctok:.0f} completion tok, calib {k_cal:.2f}; "
              f"new mean {sum(per) / len(per):.5f} $/call")
    old_ctx = sum(sum(len(m["content"]) for m in x["prompt"][:-1]) for x in old) / len(old)
    arm = total / len(cells)
    print(f"{new.name}: {len(ctx_new)} contexts in {len(cells)} cells, mean {sum(ctx_new) / len(ctx_new):.0f} chars "
          f"(old {old_ctx:.0f}, ×{sum(ctx_new) / len(ctx_new) / old_ctx:.2f})")
    for label, f in (("expected", 1.0), ("high ×1.5", 1.5)):
        need = max(0.005 * 4 * max(cells.values()) * 1.3, (len(cells) - 1) * arm * f + 1.3 * arm * f)
        print(f"{label}: ${total * f:.2f}; the runner's checks need a cap of ${need:.2f} (registered ${cap:.2f}: "
              f"{'fits' if need <= cap else 'TOO SMALL'})")


if __name__ == "__main__":
    {"first": first, "switch": switch, "anchor": anchor, "estimate": estimate}[sys.argv[1]]()
