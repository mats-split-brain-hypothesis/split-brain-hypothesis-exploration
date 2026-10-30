"""Passage → readouts: one item of one bank, read at one cell by the plain J-lens and every centred variant side by
side, then the same cell across layers. Arms are discovered from out/eval/<family>/<split>/; their names and
colours come from catalog.py (one line per new centring). Hits use the pipeline's strict rule (jlm.score); judge
verdicts come from the newest full judge run of each arm. Controls (jlm.controls): a toggle swaps in each arm's
prompt-masked top 10, readout tokens that are the item's prompt-content forms (echo) are marked, and the model's own
next-token top 10 at the read cell shows as an extra card when evaluate.py wrote it.

Laid out to fit one screen: controls in two rows, then passage + cell picker | verdicts (side-by-side panels past 8
centres), the readout cards in one row, the depth chart | layer table, then how μ is chosen at the cell: the
reference pool in its top PCs with the cells a centre averages highlighted (jlm.centres' optional members()) | their list. Explanations sit behind hover help rather than in captions."""

import math
import re

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import catalog
import nights
import gloss
import sources
import ui

# A working page: tighter vertical rhythm than the reading pages.
st.html("""<style>
.block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; }
.block-container [data-testid="stVerticalBlock"] { gap: .55rem; }
.jm-passage.tok { font-size: 16px; line-height: 1.65; max-height: 250px; padding: 12px 16px; }
.jm-spec.facts { grid-template-columns: max-content minmax(0, 1fr); gap: 4px 18px; margin-top: 8px; font-size: 13.5px; }
.jm-spec.facts dt { font-size: 10.5px; padding-top: 2px; }
.jm-rgrid { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.jm-rcard { padding: 9px 11px 10px; gap: 6px; }
.jm-rcard .nm { font-size: 13.5px; }
.jm-rcard li { font-size: 12.5px; padding: 1px 4px; grid-template-columns: 14px minmax(0, 1fr) clamp(64px, 30%, 150px); gap: 6px; }
.jm-rcard .meta { font-size: 11.5px; }
.jm-rcard .jm-pill { font-size: 11px; line-height: 1.6; }
.jm-table.compact th { padding: 6px 10px; }
.jm-table.compact td { padding: 5px 10px; font-size: 13px; }
.jm-layers td { padding: 3px 8px; }
.jm-vpanels { display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 10px; align-items: start; }
@media (max-width: 1100px) { .jm-vpanels { grid-template-columns: minmax(0, 1fr); } }
.jm-verdicts { table-layout: auto; }
.jm-verdicts th { padding: 5px 8px; }
.jm-verdicts td { padding: 3px 8px; font-size: 12.5px; }
.jm-vpanels[style*="--n:2"] .jm-verdicts :is(th, td), .jm-vpanels[style*="--n:3"] .jm-verdicts :is(th, td) { padding-left: 6px; padding-right: 6px; }
.jm-vm { color: var(--muted); font-size: 13px; line-height: 1; }
.jm-vm.ok { color: var(--good); }
.jm-vm.form { color: var(--good); opacity: .75; }
.jm-pill.form { color: var(--good); background: none; outline: 1px dashed color-mix(in srgb, var(--good) 70%, transparent);
  outline-offset: -1px; }
.jm-verdicts td:first-child { max-width: 0; width: 100%; }
.jm-verdicts .jm-armtag { display: flex; min-width: 0; }
.jm-verdicts .jm-armtag .nm { overflow: hidden; text-overflow: ellipsis; }
.jm-verdicts .jm-pill { font-size: 10.5px; line-height: 1.5; padding: 0 7px; gap: 5px; }
.jm-verdicts .jm-pill::before { width: 6px; height: 6px; }
div[class*="st-key-jmchart_ex_rank"] .nsewdrag { cursor: pointer !important; }
.jm-layers .jm-chip { font-size: 11px; padding: 0 5px; }
.jm-rcard li.echo .t, .jm-chip.echo { text-decoration: underline dotted var(--warn); text-underline-offset: 3px; }
.jm-chip.echo:not(.hit) { color: var(--warn); }
.jm-rcard.next { border-top-style: dashed; background: var(--sunk); }
.jm-rcard li .t .gl, .jm-chip .gl { font: 11px var(--f-body); color: var(--muted); margin-left: 6px; white-space: nowrap; }
.jm-chip .gl { font-size: 10.5px; margin-left: 4px; }
.jm-chip.hit .gl { color: var(--delta); opacity: .8; }
.jm-passage.tok span.rd { cursor: pointer; border-radius: 3px; }
.jm-passage.tok span.rd:hover { background: var(--h-soft); color: var(--h); box-shadow: inset 0 -2px 0 var(--h); }
body:has(.jm-passage .rd:hover) .jm-passage.tok span.sel:not(:hover) {
  background: none; color: inherit; box-shadow: inset 0 -2px 0 color-mix(in srgb, var(--h) 45%, transparent); }
.jm-pv { display: none; }
div[class*="st-key-ex_pick_"] { display: none; }
</style>""")

ui.page_header(
    "Explore", "Passage → readouts",
    "Pick an item and a read cell; the plain J-lens and each centred variant read it side by side. Teal tokens are "
    "accepted targets under the pipeline's strict rule. Use Show to find the items where centring changes the answer.",
)

fams = sources.families_with_readouts()
if not fams:
    st.info("No readouts under out/eval yet: run experiments/evaluate.py first.")
    st.stop()

# ------------------------------------------------------------------ controls: two rows
qp = st.query_params
row1 = st.columns([1.4, 1.1, 0.75, 0.9, 1.3, 1.1, 0.9, 0.9], vertical_alignment="bottom")
row2 = st.columns([1, 1.25, 0.42], vertical_alignment="bottom")

fam_q = qp.get("family")
family = row1[0].selectbox("Family", fams, index=fams.index(fam_q) if fam_q in fams else 0, key="ex_family")
splits = sources.splits_with_readouts(family)
split_default = qp.get("split") if qp.get("split") in splits else ("val" if "val" in splits else splits[0])
split = row1[1].segmented_control("Split", splits, default=split_default, key=f"ex_split_{family}") or split_default
readout = row1[2].segmented_control("Readout", ["cos", "rms"], default="cos", key="ex_readout") or "cos"

dirs = {catalog.from_dir(d): d for d in sources.arm_dirs(family, split)}
arms = sorted((catalog.parse(n) for n in dirs if catalog.parse(n).readout == readout), key=lambda a: a.sort_key)
if not arms:
    st.info(f"No {readout} arms for {family}/{split}.")
    st.stop()
by_name = {a.name: a for a in arms}
held_ref = "self" if split == "fit" else "fit"  # the held-out reference for this split
default_arms = catalog.defaults(arms, held_ref)
# Night 2's best candidates get their own group beside Anthony's best candidates, ranked best first (nights.Picker)
picker = nights.Picker(arms, held_ref, sources.stamp())
with row2[0]:  # one row per group: the baselines, then each person's centres (catalog.group)
    chosen_names = picker.pills(
        "Centres", default_arms, key=f"ex_arms_{family}_{split}_{readout}",
        help="LOO: leave-one-out mean on the read bank itself. fit: fitted on the dev fit split, so held out from val and bench. "
             "J++ arms read through the J++ lens instead of the J-lens, for comparison. "
             + " ".join(f"{a.label}: {a.blurb}" for a in arms if not a.ref or a.ref == held_ref),
    )
chosen = [by_name[n] for n in chosen_names]
if not chosen:
    st.info("Select at least one centre.")
    st.stop()

has_masked = {a.name for a in chosen if sources.has_masked(family, split, dirs[a.name])}
masked = row1[7].toggle(
    "Masked", value=False, key="ex_masked", disabled=not has_masked,
    help="Show each arm's prompt-masked top 10: the next ten after every vocabulary token that is a prompt-content form "
         "of the item is removed (jlm.controls). Strict verdicts, hits and ✓ cells follow the masked top 10. A gain that "
         "vanishes here was reading the prompt. Arms evaluated before the control suite have no masked readout and keep "
         "their plain top 10." if has_masked else "No selected arm has a prompt-masked readout yet (evaluate.py writes masked.jsonl).")
masked = bool(masked and has_masked)
KIND = {a.name: "masked" if masked and a.name in has_masked else "readouts" for a in chosen}
mt = {a.name: sources.readouts_mtime(family, split, dirs[a.name], KIND[a.name]) for a in chosen}
C = {a.name: sources.cells(family, split, dirs[a.name], mt[a.name], KIND[a.name]) for a in chosen}
R = {a.name: sources.ranks(family, split, dirs[a.name], sources.readouts_mtime(family, split, dirs[a.name])) for a in chosen}
HIT = {a.name: sources.hit_cells(family, split, dirs[a.name], mt[a.name], KIND[a.name]) for a in chosen}
# cells whose top 10 holds only another form of the target (swims for swimming): a pass under strict + forms only
FHIT = {a.name: {i: [c for c in cs if c not in set(HIT[a.name].get(i, []))]
                 for i, cs in sources.hit_cells(family, split, dirs[a.name], mt[a.name], KIND[a.name], with_forms=True).items()}
        for a in chosen}
SEMV = {a.name: sources.is_sem(family, split, dirs[a.name]) for a in chosen}  # read over the semantic vocabulary
J = {}  # arm -> its newest full judge run on this bank, if any
for a in chosen:
    runs = sources.judge_runs(family, split, dirs[a.name])
    if runs:
        J[a.name] = sources.judged(family, split, dirs[a.name], runs[0], mt[a.name])
B = sources.bank(family, split)
items = B["items"]

present = {k[0] for k in C[chosen[0].name]}
ids = [i for i in items if i in present]
plain = next((a for a in chosen if a.centre == "zero" and a.lens == "jlens"), None)
centred = [a for a in chosen if a is not plain]  # every other arm, J++ ones included
proxy = family in sources.STRICT_IS_PROXY

FORMS = "strict + forms"  # strict, with the target's other forms accepted too (jlm.forms; single-token families)
free = ["strict"] if family in sources.MT_FAMILIES else ["strict", FORMS]
scorer = free[-1]
if J or len(free) > 1:
    scorer = row1[3].segmented_control(
        "Pass by", free + (["judge"] if J else []), default=free[-1] if proxy or not J else "judge",
        key=f"ex_scorer_{family}_{split}",
        help="Which verdict drives the item marks, the filters and the ✓ cells. strict + forms: another form of the "
             "target counts too (swims for swimming; in association also derived words such as swimmer)."
             + (" The judge is Haiku 5.5 (development, unpinned); only judged arms have it." if J else " No judge run here.")
             + ("" if proxy or not J else " Multi-token family: 'strict' here is the distinctive-piece proxy (jlm.mtproxy), "
                "and the judge reads each bag through the bench's summarizer and regex." if family in sources.MT_FAMILIES
                else " Strict is not a proxy for the judge on this family: it misses inferred and multi-token answers."),
    ) or free[-1]
else:
    row1[3].html('<div style="font-size:12.5px;color:var(--muted);padding-bottom:9px">Pass by strict<br>(no judge run)</div>')


def passes(a, i) -> bool | None:
    """Item verdict under the chosen scorer; None when that arm has no judge verdict for the item."""
    if scorer == "judge":
        it = J.get(a.name, {}).get("items", {}).get(i)
        return None if it is None else it["pass"]
    return bool(HIT[a.name].get(i) or (scorer == FORMS and FHIT[a.name].get(i)))


SHOW = {  # arms without a verdict (not judged) are left out of each comparison
    "All items": lambda i: True,
    "Centring helps": lambda i: plain is not None and passes(plain, i) is False and any(passes(a, i) is True for a in centred),
    "Centring hurts": lambda i: plain is not None and passes(plain, i) is True and any(passes(a, i) is False for a in centred),
    "Every arm passes": lambda i: all(passes(a, i) is not False for a in chosen) and any(passes(a, i) for a in chosen),
    "No arm passes": lambda i: not any(passes(a, i) for a in chosen),
}
show = row1[4].selectbox("Show", list(SHOW), key="ex_show",
                         help="Helps / hurts compare the plain lens with the selected centred arms, under the Pass-by scorer, any layer.")
subs = sorted({items[i].get("subfamily") for i in ids if items[i].get("subfamily")})
sub = row1[5].selectbox("Subfamily", ["all", *subs], key=f"ex_sub_{family}_{split}") if subs else "all"
scored_only = row1[6].toggle("Scored only", value=True, key="ex_scored",
                             help="Leave out items the strict scorer excludes (leaky, unreachable, implicit).") if B["scored"] else False
pool = [i for i in ids if SHOW[show](i) and (sub == "all" or items[i].get("subfamily") == sub)
        and (not scored_only or i in B["scored"])]
if show in ("Centring helps", "Centring hurts") and plain is None:
    st.info("“Centring helps / hurts” compares against the plain J-lens: select Plain J-lens under Centres.")
    st.stop()
if not pool:
    st.info("No item matches these filters.")
    st.stop()


def snippet(i: str) -> str:
    sp = B["specs"].get(i, {})
    text = sp.get("text") or next((m["content"] for m in reversed(sp.get("messages") or []) if m["role"] == "user"), "")
    text = " ".join(text.split())
    return text if len(text) <= 64 else "…" + text[-63:]


def form_pass(a, i) -> bool:
    """Whether arm a passes item i only through another form of its target (strict + forms, not strict)."""
    return not HIT[a.name].get(i) and bool(FHIT[a.name].get(i))


def item_label(i: str) -> str:
    marks = "".join("≈" if passes(a, i) is False and scorer == "strict" and form_pass(a, i)
                    else {True: "✓", False: "·", None: "?"}[passes(a, i)] for a in chosen)
    return f"{marks}   {i} · {snippet(i)} → {', '.join(B['targets'].get(i, [])[:3])}"


key_item = f"ex_item_{family}_{split}"
if st.session_state.get(key_item) not in pool:
    st.session_state[key_item] = qp.get("item") if qp.get("item") in pool else pool[0]


def step(d: int):
    k = pool.index(st.session_state[key_item])
    st.session_state[key_item] = pool[(k + d) % len(pool)]


english = row2[2].toggle("English", value=True, key="ex_gloss",
                         help="The closest English next to non-English tokens, from a one-time table "
                              "(data/gloss/en.json, Haiku 5.5 over the whole vocabulary). A reading aid only: never "
                              "used in scoring, and fragments are glossed as the word they probably belong to (…).")
with row2[1]:
    p1, p2, p3 = st.columns([12, 1, 1], vertical_alignment="bottom", gap="small")
    item = p1.selectbox(f"Item · {len(pool)} of {len(ids)}", pool, format_func=item_label, key=key_item,
                        help=f"Marks: one per selected centre, in order, by {scorer}: ✓ pass, · no pass"
                             + (", ≈ passes only through another form of the target (strict + forms)" if scorer == "strict" else "")
                             + (", ? not judged." if scorer == "judge" else "."))
    p2.button("", icon=":material/arrow_back:", on_click=step, args=(-1,), key="ex_prev", help="Previous item", width="stretch")
    p3.button("", icon=":material/arrow_forward:", on_click=step, args=(1,), key="ex_next", help="Next item", width="stretch")
st.query_params.update({"family": family, "split": split, "item": item})

it, spec, targets = items[item], B["specs"].get(item, {}), B["targets"].get(item, [])
forms = set(B["forms"].get(item, []))
extra = set(B["extra"].get(item, []))  # other forms of the target: a pass under strict + forms only
echo_forms = sources.prompt_forms(family, split).get(item, frozenset())  # the item's prompt-content forms (echo)
NXT = sources.next_tokens(family, split, sources.next_mtime(family, split))


def tok_cls(t: str) -> str:
    """CSS classes for a readout token: an accepted target (hit) or another form of it (formhit, dashed), and / or a
    prompt-content form (echo)."""
    return " ".join(c for c in (sources.hit_kind(family, t, forms, extra), "echo" if sources.is_echo(t, echo_forms) else "") if c)
cells_here = sorted({(L, p) for (i, L, p) in C[chosen[0].name] if i == item})
positions = sorted({p for _, p in cells_here})
layers = sorted({L for L, _ in cells_here})
pos_tok = {p: C[chosen[0].name][item, L, p]["token"] for L, p in cells_here}


def vis(tok: str) -> str:
    t = sources.decode_token(tok)
    return t.replace("\n", "↵") if t.strip() else (t.replace(" ", "␣").replace("\n", "↵") or "∅")


def passage_html(sel: int) -> str:
    """The prompt as the model read it, token by token: read cells underlined, the selected one filled.
    Chat-template tokens are shown small; falls back to the bank's text when no tokenizer is cached."""
    toks = sources.rendered(family, split, item)
    if toks is None:
        text = spec.get("text") or "\n\n".join(f"{m['role']}: {m['content']}" for m in spec.get("messages") or [])
        return f'<div class="jm-passage">{ui.esc(text)}</div>'
    # multihop's offset-from-end items store negative positions: index from the end, as the capture did
    marked = {p if p >= 0 else len(toks) + p: p for p in positions}  # index -> the stored position (data-p)
    sel = sel if sel >= 0 else len(toks) + sel
    out = []
    for k, t in enumerate(toks):
        special = (t.startswith("<|") and t.endswith("|>")) or t in ("<think>", "</think>")
        read = k in marked
        cls = " ".join(c for c in ("sp" if special else "", "rd" if read else "", "sel" if k == sel else "") if c)
        # whitespace stays invisible except on read cells, where it is the token being read
        body = ui.esc(t) if t.strip() or not read else t.replace(" ", "␣").replace("\n", "↵\n")
        # read cells: hover previews their readouts below (pv_css), a click picks the cell (PICK)
        attrs = f' data-p="{marked[k]}" title="read cell · position {k} · hover to preview, click to pick"' if read else f' title="position {k}"'
        out.append(f'<span class="{cls}"{attrs}>{body}</span>' if cls else body)
    return '<div class="jm-passage tok">' + "".join(out) + "</div>"


# Clicks on the passage's read tokens, sent back as a trigger (the passage itself is plain st.html). Each click carries a
# nonce so picking the same token twice still reruns.
PICK = st.components.v2.component("ex_passage_pick", js="""
export default function({ setTriggerValue }) {
  const onClick = (e) => {
    const t = e.target.closest('.jm-passage .rd[data-p]');
    if (t) setTriggerValue('pick', { p: t.dataset.p, n: Date.now() });
  };
  document.addEventListener('click', onClick);
  return () => document.removeEventListener('click', onClick);
}""")


def pass_cells(a) -> list[tuple[int, int]]:
    """This item's passing cells for one arm under the Pass-by scorer (judge cells with no position: the read cell)."""
    if scorer == "judge":
        cells = J.get(a.name, {}).get("items", {}).get(item, {}).get("cells", {})
        return sorted((L, positions[-1] if p is None else p) for (L, p), v in cells.items() if v["pass"])
    return sorted(HIT[a.name].get(item, []) + (FHIT[a.name].get(item, []) if scorer == FORMS else []))


# ------------------------------------------------------------------ passage + cell picker | verdicts
VERDICT_ROWS = 8  # more centres than this split into side-by-side verdict panels (column-major, at most 3)
n_panels = min(3, math.ceil(len(chosen) / VERDICT_ROWS))
left, right = st.columns({1: [1.05, 1], 2: [1, 1.9], 3: [1, 2.4]}[n_panels], gap="large")
with left:
    ui.label("Passage", "as the model read it · read cells underlined")
    passage_slot = st.empty()  # filled once the read position is known
    facts = [("targets", " ".join(f'<span class="jm-chip hit">{ui.esc(t)}</span>' for t in targets) or "–")]
    for k, lab in (("subfamily", "subfamily"), ("concept", "concept"), ("polarity", "instruction"), ("attr_class", "attribute")):
        if it.get(k):
            facts.append((lab, ui.esc(str(it[k]).replace("_", " "))))
    if B["scored"] is not None and item not in B["scored"]:
        facts.append(("scoring", '<span style="color:var(--warn)">excluded by the strict scorer (leak, unreachable or implicit)</span>'))
    if spec.get("note"):
        facts.append(("read cells", ui.esc(spec["note"])))
    st.html('<dl class="jm-spec facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>")

    ui.label("Read cell", "✓ some selected centre passes " + {"judge": "(judge)", FORMS: "(strict + forms)"}.get(
        scorer, "(strict) · ≈ only another form"))
    any_hit = {c for a in chosen for c in pass_cells(a)}
    form_hit = {c for a in chosen for c in FHIT[a.name].get(item, [])} - any_hit if scorer == "strict" else set()

    def mark(cs) -> str:
        return " ✓" if cs & any_hit else " ≈" if cs & form_hit else ""
    first_c = next((c for a in centred for c in pass_cells(a)), None) or next(iter(sorted(any_hit)), None)
    pos = positions[-1]
    if len(positions) > 1:
        pos_key = f"ex_pos_{family}_{split}_{item}"
        if pos_key not in st.session_state:
            st.session_state[pos_key] = first_c[1] if first_c else positions[-1]
        # a click on a read token in the passage picks that cell here, at the layer it was previewed at
        picked = PICK(key=f"ex_pick_{family}_{split}_{item}", on_pick_change=lambda: None).pick
        if picked is not None and int(picked["p"]) in positions:
            p_old, p_new = st.session_state.get(pos_key) or positions[-1], int(picked["p"])
            L_old = st.session_state.get(f"ex_layer_{family}_{split}_{item}_{p_old}")
            st.session_state[pos_key] = p_new
            if L_old in layers:
                st.session_state[f"ex_layer_{family}_{split}_{item}_{p_new}"] = L_old
        pos = st.pills("Position", positions, label_visibility="collapsed",
                       format_func=lambda p: f"{vis(pos_tok[p])}" + mark({(L, p) for L in layers}),
                       key=pos_key) or positions[-1]
    layer_default = first_c[0] if first_c and first_c[1] == pos else (44 if 44 in layers else layers[-1])
    layer_key = f"ex_layer_{family}_{split}_{item}_{pos}"
    if st.session_state.get(layer_key) not in layers:
        st.session_state[layer_key] = layer_default
    layer = st.select_slider("Layer", layers, key=layer_key,
                             label_visibility="collapsed", format_func=lambda L: f"L{L}" + mark({(L, pos)}))

with right:
    tip = (f"Strict: over {len(layers)} layers × {len(positions)} read position{'s' if len(positions) > 1 else ''}, an item passes "
           "if any cell has an accepted target in its top 10. Form pass: only another form of the target is in a top 10 "
           "(swims for swimming): a pass under strict + forms, not under strict. First hit: earliest passing layer · "
           "passing cells (for a form pass, its cells). "
           "Best: the target's best place in the full vocabulary (#1 = top; #1–#10 is a pass)."
           + (f" Judge: {next(iter(J.values()))['label']} (development judge, unpinned)." if J else "")
           + (f" More than {VERDICT_ROWS} centres split into side-by-side panels, read down each panel in order."
              if n_panels > 1 else ""))
    if n_panels == 1:
        yes, no = '<span class="jm-pill done">pass</span>', '<span class="jm-pill todo">no pass</span>'
        via = '<span class="jm-pill form" title="passes only through another form of the target">form pass</span>'
    else:  # panels are narrow: a filled / hollow dot in place of the pill
        yes, no = '<span class="jm-vm ok" title="pass">●</span>', '<span class="jm-vm" title="no pass">○</span>'
        via = '<span class="jm-vm form" title="form pass: only another form of the target">◐</span>'
    rows, n_strict, n_forms, n_judge = [], 0, 0, 0
    for a in chosen:
        hc = HIT[a.name].get(item, []) or FHIT[a.name].get(item, [])
        rk = [r for (i, L, p), r in R[a.name].items() if i == item and r >= 0]
        n_strict += bool(HIT[a.name].get(item))
        n_forms += bool(hc)
        row = [f'<span class="jm-armtag" title="{ui.esc(a.label)}"><i style="background:{a.colour}"></i>'
               f'<span class="nm">{ui.esc(a.label)}</span></span>',
               yes if HIT[a.name].get(item) else via if hc else no,
               (f"L{hc[0][0]} <span style='color:var(--muted)'>· {len(hc)}</span>" if hc else "–"), f"#{min(rk) + 1}" if rk else "–"]
        if J:
            ji = J.get(a.name, {}).get("items", {}).get(item)
            n_judge += bool(ji and ji["pass"])
            row.insert(2, '<span style="color:var(--muted)" title="not judged">n/j</span>' if ji is None else yes if ji["pass"] else no)
        rows.append(row)
    tally = (f"strict {n_strict}/{len(chosen)}" + (f" · + forms {n_forms}/{len(chosen)}" if n_forms > n_strict else "")
             + (f" · judge {n_judge}/{len(chosen)}" if J else ""))
    ui.label(f'Item verdicts <span class="jm-help" title="{ui.esc(tip)}">ⓘ</span>',
             f"{tally} · {len(layers)} layers × {len(positions)} position{'s' if len(positions) > 1 else ''}")
    head = ["centre", "strict", *(["judge"] if J else []), "first hit", "best"]
    if n_panels > 1:  # short headers, full names on hover
        head = ["centre", '<span title="strict">S</span>', *(['<span title="judge">J</span>'] if J else []),
                '<span title="first hit">first</span>', "best"]
    num = {len(head) - 1}
    th = "".join(f'<th{" class=num" if k in num else ""}>{h}</th>' for k, h in enumerate(head))
    per = math.ceil(len(rows) / n_panels)  # column-major: read down the first panel, then the next
    panels = "".join(
        f'<div class="jm-wrap"><table class="jm-table compact jm-verdicts"><thead><tr>{th}</tr></thead><tbody>'
        + "".join("<tr>" + "".join(f'<td{" class=num" if k in num else ""}>{v}</td>' for k, v in enumerate(r)) + "</tr>"
                  for r in rows[s:s + per])
        + "</tbody></table></div>" for s in range(0, len(rows), per))
    st.html(f'<div class="jm-vpanels" style="--n:{n_panels}">{panels}</div>')
passage_slot.html(passage_html(pos))


def gl(tok: str) -> str:
    g = gloss.gloss(sources.decode_token(tok)) if english else None
    return f'<span class="gl">{ui.esc(g)}</span>' if g else ""


# ------------------------------------------------------------------ readouts at this cell
def geo(a) -> dict | None:
    """This arm's per-cell geometry (jlm.geometry from the captures); None for the plain lens or with no capture."""
    if a.centre == "zero":
        return None
    try:
        return sources.geometry(family, split, a.centre, a.ref, sources.captures_mtime(family, split, a.ref))
    except FileNotFoundError:
        return None


G = {a.name: geo(a) for a in chosen}


def keep_txt(a, pos: int) -> str:
    """‖h − μ‖ / ‖h‖ at this cell, with the rest of μ's geometry behind a hover."""
    if a.centre == "zero":
        return '<span title="μ = 0: the plain lens reads all of h">‖h−μ‖/‖h‖ 1.00</span>'
    g = (G[a.name] or {}).get((item, layer, pos))
    if g is None:
        return ""
    tip = (f"‖h‖ {g['norm_h']:.1f} · ‖μ‖ {g['norm_mu']:.1f} · ‖h−μ‖ {g['norm_x']:.1f} · cos(h, μ) {g['cos']:.2f} · "
           f"μ averages {g['support']} reference cells" + (" (fell back to the family mean)" if g["fallback"] else ""))
    return f'<span title="{ui.esc(tip)}">‖h−μ‖/‖h‖ <b style="color:var(--ink)">{g["norm_x"] / g["norm_h"]:.2f}</b></span>'


def top_list(tokens: list[str], sc: list[float]) -> str:
    lo, hi = min(sc), max(sc)
    lis = []
    for k, (t, s) in enumerate(zip(tokens, sc, strict=False), 1):
        w = 12 + 88 * ((s - lo) / (hi - lo) if hi > lo else 1)
        echo = ' title="a prompt-content form of this item (echo)"' if sources.is_echo(t, echo_forms) else ""
        lis.append(f'<li class="{tok_cls(t)}"{echo}><span class="k">{k}</span><span class="t">{ui.esc(vis(t))}{gl(t)}</span>'
                   f'<span class="s"><span class="bar" style="width:{w:.0f}%"></span><span class="v">{s:.2f}</span></span></li>')
    return "<ol>" + "".join(lis) + "</ol>"


def echo_txt(tokens: list[str]) -> str:
    """Echo at this cell: how many of the top 10 are the item's prompt-content forms."""
    if not echo_forms:
        return ""
    n = sum(sources.is_echo(t, echo_forms) for t in tokens)
    return (f'<span title="echo: {n} of the top {len(tokens)} are prompt-content forms of this item (dotted underline)"'
            f'{" style=color:var(--warn)" if n else ""}>echo {n}</span>')


def next_card(pos: int) -> str:
    """The model's own next-token top 10 at this read cell (the next-token baseline; independent of the layer)."""
    r = NXT.get((item, pos))
    if r is None:
        return ""
    sc = r.get("scores") or [0.0] * len(r["tokens"])
    hit_here = any(sources.is_hit(family, t, forms) for t in r["tokens"])
    status = ('<span class="jm-pill done">names a target</span>' if hit_here else '<span class="jm-pill todo">no target</span>')
    tip = ("The model's own next-token top 10 at this read cell (final layer through the unembedding), the same at every "
           "layer. A centred readout that matches it is reading the model's next token, not what it holds unsaid.")
    return (f'<div class="jm-rcard next" style="--c:var(--muted)" title="{ui.esc(tip)}"><div class="hd"><span class="nm">'
            f'Model\'s next token</span><span class="sub">L{r.get("layer", "")} logits</span></div><div class="meta">{status}'
            f'{echo_txt(r["tokens"])}</div>{top_list(r["tokens"], sc)}</div>')


def card(a, pos: int) -> str:
    r = C[a.name].get((item, layer, pos))
    rk = R[a.name].get((item, layer, pos))
    if r is None:
        body = '<div class="jm-empty">no readout at this cell</div>'
        status = ""
    else:
        sc = r["scores"] or [0.0] * len(r["tokens"])
        body = top_list(r["tokens"], sc)
        hit_here = any(sources.is_hit(family, t, forms) for t in r["tokens"])
        status = ('<span class="jm-pill done">in top 10</span>' if hit_here else '<span class="jm-pill todo">not in top 10</span>')
        status += echo_txt(r["tokens"])
    rank_txt = "" if rk is None else ("no single-token target" if rk < 0 else f"target #{rk + 1}")
    foot = ""
    if a.name in J:
        ji = J[a.name]["items"].get(item, {}).get("cells", {})
        v = ji.get((layer, pos)) or (ji.get((layer, None)) if pos == positions[-1] else None)  # no position: the read cell
        if v is None:
            foot = '<div class="jv"><span class="jm-pill todo">judge: not judged here</span></div>'
        else:
            pill = ('<span class="jm-pill done">judge: pass</span>' if v["pass"]
                    else f'<span class="jm-pill todo">judge: {ui.esc(v.get("pick") or "no pass")}</span>')
            ev = f'<div class="ev">“{ui.esc(v["evidence"])}”</div>' if v.get("evidence") else ""
            why = f'<div class="why">{ui.esc(v["why"])}</div>' if v.get("why") else ""
            foot = f'<div class="jv">{pill}{ev}{why}</div>'
    return (f'<div class="jm-rcard" style="--c:{a.colour}"><div class="hd"><span class="nm">{ui.esc(a.label)}</span>'
            f'<span class="sub">{ui.esc(a.readout)}{" · masked" if KIND[a.name] == "masked" else " · plain (no masked)" if masked else ""}{" · semantic vocab" if SEMV[a.name] else ""}</span></div><div class="meta">{status}<span>{rank_txt}</span>{keep_txt(a, pos)}</div>{body}{foot}</div>')


def pv_css() -> str:
    """Hover a read cell in the passage to show its readouts, otherwise the picked cell. Pure CSS (body:has), so moving
    along the passage needs no rerun; the layer stays the slider's. The Read cell pill of the hovered token is outlined
    (pills are in position order) so the picker and the cards agree while hovering."""
    q = lambda p: f'[data-p="{p}"]'
    pills = f'div[class*="st-key-ex_pos_{family}_{split}_{item}"] button'
    rules = ["body:not(:has(.jm-passage .rd:hover)) .jm-pv.cur { display: contents; }"]
    for k, p in enumerate(positions, 1):
        rules.append(f"body:has(.jm-passage .rd{q(p)}:hover) .jm-pv{q(p)} {{ display: contents; }}")
        rules.append(f"body:has(.jm-passage .rd{q(p)}:hover) {pills}:nth-of-type({k}) "
                     "{ box-shadow: 0 0 0 2px var(--h); }")
    return "<style>" + "\n".join(rules) + "</style>"


def pv(p: int, html: str) -> str:
    return f'<span class="jm-pv{" cur" if p == pos else ""}" data-p="{p}">{html}</span>'


def where(p: int) -> str:
    return f"L{layer} · “{ui.esc(vis(pos_tok[p]))}” · " + (f"position {p}" if p >= 0 else f"token {-p} from the end")


bars_tip = ("Hover a read token in the passage (underlined) to preview its readouts here; click it to pick that cell. Bars scale each card's scores between its own #10 and #1: compare lengths within a card, not across "
            "cards (plain and centred scores live on different scales).")
bars_tip += (" Dotted underline: a prompt-content form of the item (echo, jlm.controls)." if echo_forms else "")
st.html(pv_css()
        + f'<div class="jm-label"><span>Readouts <span class="jm-help" title="{ui.esc(bars_tip)}">ⓘ</span></span><span class="r">'
        + "".join(pv(p, where(p)) for p in positions) + (" · prompt-masked top 10" if masked else "") + "</span></div>"
        + "".join(pv(p, '<div class="jm-rgrid">' + "".join(card(a, p) for a in chosen) + next_card(p) + "</div>")
                  for p in positions))


# ------------------------------------------------------------------ across layers: tracked tokens | table
# Which tokens to follow: the target (its stored rank, or a multi-token target's first piece), on directed_modulation
# the content words of this item's instruction and the mental-state groups in catalog.WATCH, and any word typed in.
# Every candidate is read live at this cell (sources.cell_scores) and offered by its best place over the selected
# arms and layers, so what surfaces here floats up; the defaults are the target and the best-placed others, at most
# MAX_PANELS small panels.
MAX_PANELS, MAX_PILLS = 4, 12
STOP = {"about", "after", "again", "also", "because", "before", "being", "between", "could", "every", "exactly", "from",
        "have", "into", "just", "like", "more", "most", "much", "only", "other", "over", "same", "sentence", "should",
        "some", "such", "than", "that", "their", "them", "then", "there", "these", "they", "this", "those", "through",
        "under", "very", "what", "when", "where", "which", "while", "will", "with", "word", "words", "would", "write",
        "your", "yours", "following", "copy", "text"}


def target_words() -> list[tuple[str, str]]:
    """(word, role) for the item's target units (concept, category, ...), else its accepted targets."""
    units = it.get("units")
    if isinstance(units, list) and units and isinstance(units[0], dict):
        out = [(u["match"][-1], u.get("role", "target")) for u in units if u.get("match")]
    else:
        out = [(t, "target") for t in targets[:2]]
    return out[:3]


def instruction_words() -> list[str]:
    """Content words of the item's instruction (the prompt before the quoted sentence), DM only."""
    if family != "directed_modulation":
        return []
    head = str(it.get("prompt", "")).split('"')[0]
    seen, out = set(), []
    for w in re.findall(r"[A-Za-z]{4,}", head):
        w = w.lower()
        if w not in STOP and w not in seen:
            seen.add(w)
            out.append(w)
    return out


def candidates() -> list[dict]:
    """[{key, label, kind, note, forms: [display tokens]}]: one panel each (a group: its best-placed form)."""
    out, taken = [], set()
    has_stored = any(r is not None and r >= 0 for a in chosen for (i, L, p), r in R[a.name].items() if i == item and p == pos)
    if has_stored:
        out.append({"key": "target", "label": "target", "kind": "target", "note": "best accepted form (stored rank)", "forms": []})
    for w, role in target_words():
        pc = sources.pieces(" " + w)
        if not pc or (len(pc) == 1 and has_stored and role == "concept"):
            taken.add(w.lower())
            continue
        lab = w if len(pc) == 1 else "·".join(x.strip() for x in pc)
        note = role + ("" if len(pc) == 1 else ", first piece")
        out.append({"key": f"t:{w}", "label": lab, "kind": "target", "note": note, "forms": [pc[0]]})
        taken.add(w.lower())
    watch = catalog.WATCH.get(family, {})
    in_groups = {w for ws in watch.values() for w in ws}
    for w in instruction_words():
        pc = sources.pieces(" " + w)
        if w in taken or w in in_groups or len(pc) != 1:
            continue
        out.append({"key": f"p:{w}", "label": f"“{w}”", "kind": "prompt", "note": "word of this instruction", "forms": pc})
    for g, ws in watch.items():
        out.append({"key": f"w:{g}", "label": g, "kind": "watch", "note": f"{g} group", "forms": [" " + w for w in ws]})
    for w in st.session_state.get(custom_key, []):
        pc = sources.pieces(" " + w)
        if pc:
            out.append({"key": f"c:{w}", "label": w if len(pc) == 1 else "·".join(x.strip() for x in pc), "kind": "custom",
                        "note": "added" + ("" if len(pc) == 1 else ", first piece"), "forms": [pc[0]]})
    return out


def arm_key(a) -> tuple[str, str, str, str]:
    return (a.centre, a.ref or "", a.readout, a.lens)


custom_key = f"ex_track_custom_{family}"
CS, live_err = None, ""
# Reading other tokens live needs the model's unembedding (2.5 GB) and the lens maps: cached on a research machine,
# downloaded on first use on the hosted dashboard (minutes, on 2 CPUs), so there it waits for the toggle below.
if "ex_live" not in st.session_state:
    st.session_state["ex_live"] = not sources.ON_SPACE
try:
    if not st.session_state["ex_live"]:
        raise RuntimeError("live reading is off (the toggle by Tracked tokens)")
    V = sources.vocab()
    if V is None:
        raise RuntimeError("the tokenizer is not in the local HF cache")
    CS = sources.cell_scores(family, split, item, pos, tuple(arm_key(a) for a in chosen), tuple(layers),
                             max(sources.captures_mtime(family, split, a.ref) for a in chosen))
except Exception as e:  # noqa: BLE001 (no lens or captures on this machine: the stored target rank only)
    live_err = f"{type(e).__name__}: {e}"
by_key = {arm_key(a): a for a in chosen}


def places(c: dict) -> tuple[dict[tuple[str, int], int], str]:
    """(arm name, layer) -> 0-based place, and the form followed (a group's best-placed form)."""
    if c["key"] == "target":
        return {(a.name, L): r for a in chosen for L in layers if (r := R[a.name].get((item, L, pos))) is not None and r >= 0}, ""
    if CS is None:
        return {}, ""
    best = None
    for f in c["forms"]:
        tid = V["ids"].get(f)
        if tid is None:
            continue
        pl = {(by_key[k].name, L): v for (k, L), v in sources.token_places(CS, tid).items()}
        if pl and (best is None or min(pl.values()) < min(best[0].values())):
            best = (pl, f)
    return best or ({}, "")


CANDS = []
for c in candidates():
    pl, form = places(c)
    if pl:
        if c["kind"] == "watch":
            c["label"] = form.strip() if form.strip() == c["key"][2:] else f"{form.strip()} ({c['key'][2:]})"
        CANDS.append({**c, "places": pl, "best": min(pl.values())})
fixed = [c for c in CANDS if c["kind"] in ("target", "custom")]
ranked = sorted((c for c in CANDS if c["kind"] not in ("target", "custom")), key=lambda c: c["best"])
offer = fixed + ranked[: max(0, MAX_PILLS - len(fixed))]
by_cand = {c["key"]: c for c in offer}

dl, dr = st.columns([1, 1.15], gap="large")
with dl:
    track_tip = ("Each token's place in the vocabulary (full, or semantic-only for arms in the semantic view) at this cell, by layer, for each selected centre (#1 = top; "
                 "the band is the top 10). Offered: the target (its stored rank, or a multi-token target's first piece, "
                 "shown split as spat·ula)"
                 + (", the content words of this item's instruction (in quotes: prompt text, so a high place is partly "
                    "echo) and mental-state groups (think, focus, avoid, …: each shown as its best-placed form)"
                    if family == "directed_modulation" else "")
                 + f", and words you add. Pills are ordered by best place over the selected centres and layers (the "
                   f"number); at most {MAX_PANELS} panels. Read live through the lens from the captures, so the first "
                   "read of a cell takes a few seconds.")
    ui.label(f'Tracked tokens by layer <span class="jm-help" title="{ui.esc(track_tip)}">ⓘ</span>',
             "click a layer to read it · log scale · band = top 10")
    t1, t2, t3 = st.columns([5, 1.3, 0.9], vertical_alignment="bottom", gap="small")
    t3.toggle("Live", key="ex_live", help="Read any token's place live through the lens at this cell. Off: each arm's "
              "stored target rank only. The first live read on a server loads the unembedding (2.5 GB) and the lens maps, "
              "which on the hosted dashboard takes minutes; on by default on a research machine.")
    default = ([c["key"] for c in fixed if c["kind"] == "target"][:2]
               + [c["key"] for c in fixed if c["kind"] == "custom"])[:MAX_PANELS]
    default += [c["key"] for c in ranked[: MAX_PANELS - len(default)] if c["key"] in by_cand][: MAX_PANELS - len(default)]
    picked = t1.pills("Tracked tokens", list(by_cand), selection_mode="multi", default=default,
                      format_func=lambda k: f"{by_cand[k]['label']}  #{by_cand[k]['best'] + 1}",
                      key=f"ex_track_{family}_{split}_{item}_{pos}_{len(offer)}", label_visibility="collapsed") or []

    def add_word(k=custom_key):
        w = st.session_state.get("ex_track_add", "").strip()
        if w and w not in st.session_state.setdefault(k, []):
            st.session_state[k] = [*st.session_state[k], w]
        st.session_state["ex_track_add"] = ""

    t2.text_input("Add a word", key="ex_track_add", on_change=add_word, placeholder="add a word",
                  label_visibility="collapsed", help="Track any word: it is added for this family, read by its first piece "
                  "when it is several tokens.")
    added = st.session_state.get(custom_key, [])
    if added:
        keep_key = f"ex_track_keep_{family}_{'|'.join(added)}"  # a new widget whenever the list changes

        def keep_words(k=custom_key, kk=keep_key):
            st.session_state[k] = list(st.session_state.get(kk, []))

        st.multiselect("Added words", added, default=added, key=keep_key, on_change=keep_words,
                       help="Words you added for this family. Remove one (×) to drop it from the tracked list everywhere "
                            "in this family; the clear button removes them all.")
    show_c = [by_cand[k] for k in by_cand if k in picked][:MAX_PANELS]
    if live_err and not CANDS:
        st.caption(f"No stored target rank here, and the live readout is unavailable ({live_err}).")
    elif not show_c:
        st.caption("Pick a token to follow." if offer else "Nothing to track at this cell.")
    else:
        n = len(show_c)
        ncols, nrows = min(n, 2), math.ceil(n / 2)
        fig = make_subplots(rows=nrows, cols=ncols, shared_xaxes=True, shared_yaxes=True, horizontal_spacing=0.05,
                            vertical_spacing=0.16 if nrows > 1 else 0.0,
                            subplot_titles=[f"<b>{ui.esc(c['label'])}</b>  <span style='font-size:11px'>{ui.esc(c['note'])}</span>"
                                            for c in show_c])
        top = 10
        for k, c in enumerate(show_c):
            r_, c_ = k // 2 + 1, k % 2 + 1
            for a in chosen:
                ys = [c["places"].get((a.name, L)) for L in layers]
                if all(y is None for y in ys):
                    continue
                top = max([top, *(y + 1 for y in ys if y is not None)])
                fig.add_trace(go.Scatter(
                    x=layers, y=[None if y is None else y + 1 for y in ys], mode="lines+markers", name=a.label,
                    legendgroup=a.name, showlegend=False, line=dict(color=a.colour, width=2, dash=a.dash),
                    marker=dict(size=5 if n > 1 else 6, color=a.colour, line=dict(color=ui.c("surface"), width=1.5)),
                    hovertemplate=f"<b>{ui.esc(a.label)}</b>: #%{{y}}<extra></extra>"), row=r_, col=c_)
        for k in range(n):  # clicking anywhere in a layer's column selects it: an invisible full-height bar per layer
            fig.add_trace(go.Bar(x=layers, y=[(top + 1) * 3] * len(layers), base=0.5, width=4, name="", showlegend=False,
                                 marker=dict(color="rgba(0,0,0,0.002)", line_width=0), hovertemplate="<extra></extra>"),
                          row=k // 2 + 1, col=k % 2 + 1)
        fig.update_traces(unselected=dict(marker=dict(opacity=1)), selected=dict(marker=dict(opacity=1)))
        fig.add_hrect(y0=0.9, y1=10.5, fillcolor=ui.rgba("delta", 0.08), line_width=0, row="all", col="all")
        fig.add_vline(x=layer, line=dict(color=ui.c("line-2"), width=1, dash="dash"), row="all", col="all")
        per = (34 * len(layers) + 30) if n == 1 else (17 * len(layers) + 70)
        ui.plot_layout(fig, per * nrows + (0 if n == 1 else 10))
        fig.update_layout(hovermode="x unified", margin=dict(l=8, r=8, t=34 if n > 1 else 28, b=8), bargap=0)
        fig.update_annotations(font=dict(size=12.5, color=ui.c("ink-2")), yshift=2)
        fig.update_xaxes(tickvals=layers, ticktext=[f"L{L}" if n == 1 or k % 2 == 0 else "" for k, L in enumerate(layers)])
        fig.update_yaxes(type="log", range=[math.log10(top) + 0.15, -0.08])
        ck = f"ex_rank_{family}_{split}_{item}_{pos}_{st.session_state.get('ex_rank_n', 0)}"

        def pick_layer(ck=ck, lk=layer_key):
            pts = st.session_state[ck].selection.points
            if pts and pts[0].get("x") in layers:
                st.session_state[lk] = pts[0]["x"]
                st.session_state["ex_rank_n"] = st.session_state.get("ex_rank_n", 0) + 1  # a fresh chart: no lingering selection

        ui.chart(fig, ck, on_select=pick_layer, selection_mode="points")
        skipped = (CS or {}).get("skipped") or {}
        if skipped:
            st.caption("Not read live (stored target rank only): " + "; ".join(
                f"{by_key[k].label} ({v.split(':')[0]})" for k, v in skipped.items() if k in by_key))
with dr:
    ui.label("Top 5 by layer", "this position · current layer highlighted")
    head = "".join(f'<th><span class="jm-armtag"><i style="background:{a.colour}"></i>{ui.esc(a.label)}</span></th>' for a in chosen)
    body = ""
    for L in layers:
        tds = ""
        for a in chosen:
            r = C[a.name].get((item, L, pos))
            tds += "<td>" + ('<div class="jm-chips">' + "".join(
                f'<span class="jm-chip {tok_cls(t)}">{ui.esc(vis(t))}{gl(t)}</span>' for t in r["tokens"][:5])
                + "</div>" if r else "–") + "</td>"
        body += f'<tr class="{"cur" if L == layer else ""}"><td class="mono">L{L}{" ✓" if (L, pos) in any_hit else ""}</td>{tds}</tr>'
    st.html(f'<div class="jm-wrap"><table class="jm-table jm-layers"><thead><tr><th>layer</th>{head}</tr></thead><tbody>{body}</tbody></table></div>')

# ------------------------------------------------------------------ how μ is chosen here: the reference cloud | members
if centred:
    ui.label("How μ is chosen at this cell",
             f"L{layer} · “{ui.esc(vis(pos_tok[pos]))}” · the reference cells a centre averages, in their top principal directions")
    by_key = {}
    for a in centred:  # μ does not depend on the map: the J-lens arm names a (centre, ref) shared with its J++ twin
        by_key.setdefault((a.centre, a.ref), a)
    keys = list(by_key)
    named = [k for k in keys if sources.has_members(k[0])]
    o1, o2, o3, o4 = st.columns([2.2, 0.8, 1.3, 1], vertical_alignment="bottom")
    pool_k = o1.selectbox(
        "Reference cells of", keys, index=keys.index(named[0]) if named else 0, format_func=lambda k: by_key[k].label,
        key=f"ex_pool_{family}_{split}",
        help="Whose reference pool to draw, and whose chosen cells to highlight. Family means, read-token means, k-means "
             "clusters and k nearest cells say which cells they average; for other centres (and the shuf./rand. controls, "
             "whose μ comes from another cell) the family's reference cells are drawn with no highlight.")
    cdims = o2.segmented_control("View", ["2D", "3D"], default="2D", key="ex_cdims") or "2D"
    axes = o3.segmented_control(
        "Axes", ["pool", "this cell"], default="pool", key="ex_caxes",
        help="pool: principal directions of the whole reference pool. this cell: those of the highlighted cells, h and "
             "every μ, which spreads out a neighbourhood the pool's directions squash.") or "pool"
    corigin = o4.toggle("Origin", value=False, key="ex_corigin", help="The plain lens's μ = 0; it can sit far off and squash the cloud.")
    try:
        CC = sources.cell_cloud(family, split, layer, item, pos, pool_k, tuple(keys), "cell" if axes == "this cell" else "pool",
                                max(sources.captures_mtime(family, split, k[1]) for k in keys))
    except Exception as e:  # a pool that is not on this machine (corpus / context captures), or a centre that cannot fit here
        st.info(f"Cannot build {by_key[pool_k].label}'s reference cloud here: {type(e).__name__}: {e}")
        CC = None
    if CC is not None:
        pa, kd = by_key[pool_k], 3 if cdims == "3D" else 2
        mem = [] if CC["members"] is None else [int(r) for r in CC["members"]]
        mset, own = set(mem), set(CC["own"])
        rest = [r for r in range(len(CC["meta"])) if r not in mset and r not in own]
        hov = [f"{ui.esc(g)} · {ui.esc(fm)} · “{ui.esc(vis(t))}”" for g, fm, t in CC["meta"]]

        def pts(fig, rows, name, **mk):
            xy = CC["pool"][rows] if rows else None
            if not rows:
                return
            kw = dict(mode="markers", name=name, text=[hov[r] for r in rows], hovertemplate="%{text}<extra>" + name + "</extra>")
            if kd == 3:
                fig.add_trace(go.Scatter3d(x=xy[:, 0], y=xy[:, 1], z=xy[:, 2], marker=dict(size=mk["size"] / 2, color=mk["color"],
                                                                                         opacity=mk.get("opacity", 1)), **kw))
            else:
                fig.add_trace(go.Scatter(x=xy[:, 0], y=xy[:, 1], marker=dict(**mk), **kw))

        def one(fig, p, name, colour, symbol, size, hover, line=None):
            kw = dict(mode="markers", name=name, text=[hover], hovertemplate="%{text}<extra></extra>")
            sym3 = {"star": "diamond-open", "diamond": "diamond", "x": "x"}[symbol]
            if kd == 3:
                fig.add_trace(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], marker=dict(size=size / 2, color=colour, symbol=sym3,
                                                                                   line=dict(color=ui.c("ink"), width=1)), **kw))
            else:
                fig.add_trace(go.Scatter(x=[p[0]], y=[p[1]], marker=dict(size=size, color=colour, symbol=symbol,
                                                                         line=dict(color=ui.c("ink"), width=1.2)), **kw))

        def seg(fig, p, q, colour, dash):
            if kd == 3:
                fig.add_trace(go.Scatter3d(x=[p[0], q[0]], y=[p[1], q[1]], z=[p[2], q[2]], mode="lines", hoverinfo="skip",
                                           line=dict(color=colour, width=3, dash=dash)))
            else:
                fig.add_trace(go.Scatter(x=[p[0], q[0]], y=[p[1], q[1]], mode="lines", hoverinfo="skip",
                                         line=dict(color=colour, width=1.6, dash=dash)))

        fig = go.Figure()
        pts(fig, rest, "reference cell", size=5, color=ui.rgba("muted", 0.28), line=dict(width=0), opacity=0.5)
        pts(fig, sorted(own), "this item's own cells (never in μ)", size=7, color=ui.rgba("warn", 0.9), symbol="circle-open",
            line=dict(width=1.4))
        pts(fig, mem, f"averaged into μ · {pa.label}", size=8, color=pa.colour, line=dict(width=0.8, color=ui.c("surface")))
        mu_p = CC["mu"][pool_k]
        if kd == 2 and 0 < len(mem) <= 64:  # spokes from μ to the cells it averages
            for r in mem:
                seg(fig, mu_p, CC["pool"][r], ui.rgba("muted", 0.35), "solid")
        for k, p in CC["mu"].items():
            a = by_key[k]
            seg(fig, p, CC["h"], a.colour, "dot")  # the read vector h − μ
            one(fig, p, f"μ · {a.label}", a.colour, "diamond", 15 if k == pool_k else 11, f"<b>μ · {ui.esc(a.label)}</b>")
        one(fig, CC["h"], "h", ui.c("ink"), "star", 17, f"<b>h</b>: {ui.esc(item)} at “{ui.esc(vis(pos_tok[pos]))}”, L{layer}")
        if corigin:
            one(fig, CC["origin"], "origin", ui.c("h"), "x", 13, "<b>origin</b>: the plain lens's μ = 0")
        ui.plot_layout(fig, 470)
        t = [f"PC{j + 1} · {CC['share'][j]:.0%}" for j in range(kd)]
        fig.update_layout(margin=dict(l=8, r=8, t=12, b=8), hovermode="closest")
        if kd == 3:
            ax = dict(backgroundcolor="rgba(0,0,0,0)", gridcolor=ui.c("line"), zerolinecolor=ui.c("line-2"), color=ui.c("muted"),
                      showspikes=False)
            fig.update_layout(scene=dict(xaxis=dict(title=t[0], **ax), yaxis=dict(title=t[1], **ax), zaxis=dict(title=t[2], **ax),
                                         aspectmode="cube"))
        else:
            fig.update_xaxes(title=dict(text=t[0], font=dict(size=12, color=ui.c("muted"))))
            fig.update_yaxes(title=dict(text=t[1], font=dict(size=12, color=ui.c("muted"))), scaleanchor="x", scaleratio=1)

        cl, cr = st.columns([2, 1], gap="large")
        with cl:
            leg = [(ui.rgba("muted", 0.5), "reference cell", "50%"), (pa.colour, f"averaged into μ ({len(mem)})", "50%")] if mem else \
                  [(ui.rgba("muted", 0.5), "reference cell", "50%")]
            leg += [(ui.c("warn"), "this item's own cells (excluded)", "50%")] if own else []
            leg += [(by_key[k].colour, f"μ · {by_key[k].label}", "2px") for k in keys] + [(ui.c("ink"), "h (this cell)", "2px")]
            st.html('<div class="jm-legend" style="font-size:12px;gap:6px 14px">' + "".join(
                f'<span><i style="background:{c};border-radius:{r}"></i>{ui.esc(n)}</span>' for c, n, r in leg) + "</div>")
            ui.chart(fig, f"ex_cloud_{family}_{split}_{item}_{layer}_{pos}_{pool_k}_{cdims}_{axes}_{corigin}_{'-'.join(k[0] for k in keys)}")
        with cr:
            npool = len(CC["meta"])
            if CC["named"]:
                ui.label(f"Averaged into μ · {ui.esc(pa.label)}", f"{len(mem)} of {npool} reference cells")
                order = sorted(range(len(mem)), key=lambda j: -CC["cos"][j]) if mem else []
                rows = "".join(
                    f'<tr><td class="mono">{ui.esc(CC["meta"][mem[j]][0])}</td><td>{ui.esc(CC["meta"][mem[j]][1].replace("_", " "))}</td>'
                    f'<td><span class="jm-chip">{ui.esc(vis(CC["meta"][mem[j]][2]))}</span></td><td class="num">{CC["cos"][j]:.2f}</td></tr>'
                    for j in order[:40])
                more = f'<div class="jm-cap" style="margin-top:6px">… and {len(mem) - 40} more, by cos(h, ·)</div>' if len(mem) > 40 else ""
                st.html('<div class="jm-wrap" style="max-height:440px;overflow-y:auto"><table class="jm-table compact">'
                        '<thead><tr><th>item</th><th>family</th><th>read token</th><th class="num">cos(h, ·)</th></tr></thead>'
                        f'<tbody>{rows}</tbody></table></div>{more}')
            else:
                ui.label("Reference pool", f"{npool} cells")
                pool_txt = ("its reference pool is drawn" if sources.has_members(pool_k[0])
                            else "the family's reference cells are drawn (the pool a family mean averages)")
                st.html(f'<div class="jm-cap">No cells are highlighted for {ui.esc(pa.label)}: {ui.esc(CC["why"])}, so '
                        f"{pool_txt} with every centre's μ.</div>")
            st.html('<div class="jm-cap" style="margin-top:8px">Dotted lines run from each μ to h: the read vector h − μ the '
                    "lens reads. Grey spokes join the highlighted μ to the cells it averages. Principal directions are fitted on "
                    + ("the whole pool." if axes == "pool" else "the highlighted cells, h and every μ.") + "</div>")
