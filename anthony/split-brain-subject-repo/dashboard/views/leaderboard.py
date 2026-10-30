"""Leaderboard: every evaluated arm on every family of one split, generated from out/eval/*/<split>/summary.json (never
hand-edited). Per arm: pass, prompt-masked pass, echo, next-token overlap and the judged pass where a full judge run
exists; and its macro-average gain against a chosen reference arm with the no-harm guardrail (families where the
paired 95 % interval lies below 0). Arms from before the control suite show "–" for the controls."""

import numpy as np
import streamlit as st

import catalog
import sources
import ui

ui.header(
    "Loop",
    "Leaderboard",
    "Every arm the pipeline has evaluated, on every family of one split, read from <code>out/eval</code> on load. The "
    "gain is the paired change in pass against the reference arm, averaged over the families both were read on; the "
    "guardrail lists the families where the arm loses outside the paired 95 % interval. Masked, echo and next-token "
    "overlap are the standard controls (notes/iteration-anthony/research-loop.md): a gain that vanishes under masking, or comes with more "
    "echo or next-token overlap, does not count. Strict and piece-proxy numbers are ours, not WorkspaceBench scores.",
)

stamp = sources.stamp()
R = sources.results(stamp)
splits = [s for s in sources.SPLITS if any(s in R[f] for f in R)]
if not splits:
    st.info("No summary.json under out/eval yet: run experiments/evaluate.py first.")
    st.stop()

c1, c2, c3, c4 = st.columns([1.1, 1, 2.2, 1.6], vertical_alignment="bottom")
split = c1.segmented_control("Split", splits, default="val" if "val" in splits else splits[0], key="lb_split") or splits[0]
readout = c2.segmented_control("Readout", ["cos", "rms", "all"], default="cos", key="lb_readout") or "cos"
fams = [f for f in [*sources.ALL_FAMILIES, *sorted(set(R) - set(sources.ALL_FAMILIES))] if split in R.get(f, {})]
names = {a for f in fams for a in R[f][split]["arms"]}
arms = sorted((catalog.parse(n) for n in names if readout == "all" or catalog.parse(n).readout == readout),
              key=lambda a: a.sort_key)
if not arms:
    st.info(f"No {readout} arms on {split}.")
    st.stop()
by_name = {a.name: a for a in arms}
ref_default = next((a.name for a in arms if a.centre == "zero" and a.lens == "jlens" and a.readout == "cos"),
                   next((a.name for a in arms if a.centre == "zero" and a.lens == "jlens"), arms[0].name))
ref_name = c3.selectbox("Reference arm", [a.name for a in arms], index=[a.name for a in arms].index(ref_default),
                        format_func=lambda n: f"{by_name[n].label} · {by_name[n].readout}", key=f"lb_ref_{split}_{readout}",
                        help="Gains are paired differences against this arm, item by item on each family's scored items.")
scope = c4.segmented_control("Families", ["all", "single-token", "multi-token"], default="all", key="lb_scope") or "all"
fams = [f for f in fams if scope == "all" or (f in sources.MT_FAMILIES) == (scope == "multi-token")]


def judged_value(f: str, a: str) -> float | None:
    adir = sources.arm_dir(a)
    runs = sources.judge_runs(f, split, adir)
    if not runs:
        return None
    return sources.judged(f, split, adir, runs[0], sources.readouts_mtime(f, split, adir))["value"]


def gain(f: str, a: str) -> dict | None:
    """Paired pass difference a - ref on family f: the summary's own diff when it has it, else rebuilt from readouts."""
    r = R[f][split]
    if a not in r["arms"] or ref_name not in r["arms"]:
        return None
    if a == ref_name:
        return {"d": 0.0, "ci": [0.0, 0.0]}
    if (d := r["diffs"].get(f"{a} - {ref_name}")) is not None:
        return d
    pa = sources.item_passes(f, split, sources.arm_dir(a), sources.readouts_mtime(f, split, sources.arm_dir(a)))
    pr = sources.item_passes(f, split, sources.arm_dir(ref_name), sources.readouts_mtime(f, split, sources.arm_dir(ref_name)))
    if pa is None or pr is None:
        return None
    p = sources.paired(pa, pr, tuple(r["scored_ids"]))
    return None if p["diff"] is None else {"d": p["diff"], "ci": p["ci95"]}


with st.spinner("Pairing arms against the reference…"):
    CELL = {}  # (family, arm) -> metrics
    for f in fams:
        for a in arms:
            v = R[f][split]["arms"].get(a.name)
            if v is None:
                continue
            fv = v.get("forms") if f not in sources.MT_FAMILIES else {"v": v["v"]}  # the piece proxy has no forms
            CELL[f, a.name] = {"pass": v["v"], "forms": (fv or {}).get("v"), "masked": v["masked"], "echo": v["echo"], "next": v["next"],
                               "judged": judged_value(f, a.name) if split != "bench" else None, "gain": gain(f, a.name)}


def tag(a) -> str:
    return f'<span class="jm-armtag"><i style="background:{a.colour}"></i>{ui.esc(a.label)}</span>'


def mean(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def f3(x, sign=False) -> str:
    return "–" if x is None else f"{x:+.3f}" if sign else f"{x:.3f}"


# ------------------------------------------------------------------ macro table
ui.section("Macro average over families", f"{split} · {len(fams)} families · reference {by_name[ref_name].label} "
           f"({by_name[ref_name].readout}). Averages run over the families each arm was read on; the gain only over "
           "families where the reference was read too.", eyebrow="Ranking")
rows = []
for a in arms:
    here = [f for f in fams if (f, a.name) in CELL]
    gs = [(f, CELL[f, a.name]["gain"]) for f in here if CELL[f, a.name]["gain"] is not None]
    harm = [f for f, g in gs if g["ci"][1] < 0]
    up = [f for f, g in gs if g["ci"][0] > 0]
    mg = mean([g["d"] for _, g in gs])
    rows.append((mg if mg is not None else -9, [
        tag(a) + f' <span style="color:var(--muted);font-size:12px">{a.readout}</span>', f"{len(here)}",
        f3(mean([CELL[f, a.name]["pass"] for f in here])), f3(mean([CELL[f, a.name]["forms"] for f in here])),
        f3(mean([CELL[f, a.name]["masked"] for f in here])),
        f3(mean([CELL[f, a.name]["echo"] for f in here])), f3(mean([CELL[f, a.name]["next"] for f in here])),
        f3(mean([CELL[f, a.name]["judged"] for f in here])),
        ("reference" if a.name == ref_name else "–" if mg is None else f'<b style="color:var({"--good" if mg > 0 else "--bad" if mg < 0 else "--ink"})">{mg:+.3f}</b>'
         f' <span style="color:var(--muted)">over {len(gs)}</span>'),
        f"{len(up)}" if gs else "–",
        ("–" if not gs or a.name == ref_name else
         '<span style="color:var(--good)">ok</span>' if not harm else
         '<span style="color:var(--bad)">' + ", ".join(ui.esc(f) for f in harm) + "</span>"),
    ]))
rows.sort(key=lambda r: -r[0])
ui.table(["arm", "families", "pass", "pass + forms", "masked pass", "echo", "next-token overlap", "judged", "macro gain",
          "wins", "guardrail (harmed)"], [r[1] for r in rows], num={1, 2, 3, 4, 5, 6, 7, 8, 9})
st.caption("pass: strict on single-token families, the distinctive-piece proxy on the multi-token ones. pass + forms: "
           "strict + forms (another form of the target counts too: swims for swimming; jlm.forms) on the single-token "
           "families, the piece proxy on the others; “–” until evaluate.py --rescore has run on the bank. masked: the same "
           "after every prompt-content form is removed from the vocabulary. echo: share of top-10 tokens that are prompt "
           "forms. next-token overlap: share of the top 10 also in the model's own next-token top 10. judged: newest full "
           "judge run (Haiku 5.5, unpinned dev judge) on the families judged. wins: families where the paired interval "
           "lies above 0. “–”: not measured for this arm (arms evaluated before the control suite).")

# ------------------------------------------------------------------ per family
ui.section("Per family", "One metric at a time, arms by family. Gain cells carry the paired 95 % interval; ▲ / ▼ mark "
           "intervals that exclude 0.", eyebrow="Detail")
METRICS = {"gain vs reference": "gain", "pass": "pass", "masked pass": "masked", "echo": "echo",
           "next-token overlap": "next", "judged": "judged"}
m1, _ = st.columns([3, 2], vertical_alignment="bottom")
metric = METRICS[m1.segmented_control("Metric", list(METRICS), default="gain vs reference", key="lb_metric") or "gain vs reference"]


def cell(f: str, a) -> str:
    c = CELL.get((f, a.name))
    if c is None:
        return '<span style="color:var(--line-2)">·</span>'
    v = c[metric]
    if v is None:
        return '<span style="color:var(--muted)">–</span>'
    if metric == "gain":
        if a.name == ref_name:
            return '<span style="color:var(--muted)">reference</span>'
        lo, hi = v["ci"]
        col = "--good" if lo > 0 else "--bad" if hi < 0 else "--ink-2"
        flag = " ▲" if lo > 0 else " ▼" if hi < 0 else ""
        return (f'<span style="color:var({col})" title="95 % CI {lo:+.2f} to {hi:+.2f}">{v["d"]:+.2f}{flag}</span>'
                f'<br><span style="color:var(--muted);font-size:11px">[{lo:+.2f}, {hi:+.2f}]</span>')
    return f"{v:.2f}"


head = ["arm", *[f'<span class="mono">{f}</span>' for f in fams]]
ui.table(head, [[tag(a) + f' <span style="color:var(--muted);font-size:12px">{a.readout}</span>', *[cell(f, a) for f in fams]]
                for a in arms], num=set(range(1, len(head))))
nt = [(f, R[f][split]["next_token"]) for f in fams if R[f][split].get("next_token")]
if nt:
    st.caption("The model's own next-token top 10 at the read cells, scored the same way: "
               + " · ".join(f"{f} {x['v']:.2f}" + (f" (echo {x['echo']:.2f})" if x.get("echo") is not None else "")
                            for f, x in nt if x.get("v") is not None)
               + ". An arm close to these is reading the model's next token.")
st.caption("“·”: the arm was not read on this family. Generated from out/eval/*/" + split + "/summary.json; gains against "
           "a reference other than the plain lens of the same readout are rebuilt from the readouts with the pipeline's "
           "scorer.")
