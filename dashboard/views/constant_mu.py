"""Constant μ: the search for one generalisable centre for the J-lens (x1-x12, notes/predictions.md; data in
dashboard/screen.py). Seven tabs: the goal; every centre, defined with its material (glossary entries, written
prompts, dictionary words); how each is fitted and tested; the evaluation and how each number is computed; each
WorkspaceBench family with an example and its results; every tested item with its top 10 per centre; and the same
families read by the other techniques the store holds (other lenses, other studies' centres)."""

import html

import plotly.graph_objects as go
import streamlit as st

import catalog
import screen
import sources
import ui

S = screen.stamp()
st.html("""<style>
.cm-chip { display:inline-block; padding:0 5px; margin:1px 2px 1px 0; border-radius:4px; font:12px 'IBM Plex Mono',monospace;
           background:var(--sunk); color:var(--ink-2); }
.cm-chip.hit { background:var(--delta-soft); color:var(--ink); font-weight:600; outline:1px solid var(--delta); }
.cm-tbl td, .cm-tbl th { vertical-align:top; white-space:normal; }
.cm-tbl td.cm-c { width:260px; max-width:260px; }
.cm-pos { color:var(--good); } .cm-neg { color:var(--bad); } .cm-mut { color:var(--muted); }
.cm-def { font-size:13px; color:var(--ink-2); }
</style>""")

ui.header(
    "Constant μ · J-lens n1000 · Qwen3.6-27B · our results, not WorkspaceBench scores",
    "One generalisable centre for the J-lens",
    "The J-lens reads <span class=\"m\">J<sub>l</sub> h<sub>l</sub></span>, a first-order expansion taken at "
    "<span class=\"m\">h = 0</span>, where no real state lives; its readouts are full of input-independent background. "
    "Centring reads <span class=\"m\">J<sub>l</sub>(h<sub>l</sub> − <span class=\"c-mu\">μ<sub>l</sub></span>)</span>: "
    "what this state holds that the reference μ does not. The family mean (other prompts of the same task) works "
    "well but needs a dataset of that task. <b>We look for a constant, generalisable μ</b>: one vector per layer that "
    "needs no data from the task being read, and would apply to a sentence on its own.",
)

TABS = st.tabs(["1 · Goal", "2 · The means", "3 · Fit and test", "4 · Evaluation", "5 · Families and results",
                "6 · Every item, top 10", "7 · Versus other techniques"])


def fmt_d(r: dict | None, ci: bool = True) -> str:
    if not r:
        return '<span class="cm-mut">–</span>'
    cls = "cm-pos" if r["ci"][0] > 0 else "cm-neg" if r["ci"][1] < 0 else "cm-mut"
    tail = f' <span class="cm-mut">[{r["ci"][0]:+.2f}, {r["ci"][1]:+.2f}]</span>' if ci else ""
    return f'<span class="{cls}">{r["diff"]:+.2f}</span>{tail}'


def rate(r: dict | None) -> str:
    return "–" if not r else f"{r['rate']:.2f}"


def share(r: dict | None, fam: dict | None) -> str:
    """A centre's gain as a share of the family mean's (where the family mean gains anything)."""
    if not (r and fam) or fam["ci"][0] <= 0:  # the family mean gains nothing reliable here: no share to take
        return "–"
    return f"{100 * r['diff'] / fam['diff']:.0f}%"


def order(names) -> list[str]:
    keys = list(screen.CENTRES)
    return sorted(names, key=lambda a: (keys.index(a.split("|")[0]) if a.split("|")[0] in keys else 99, a))


# ================================================================== 1 · goal
with TABS[0]:
    ui.section("What we are looking for", eyebrow="The goal")
    c1, c2, c3 = st.columns(3, gap="medium")
    c1.html(ui.note("key", "Constant", "One μ per layer, the same for every read: no per-item or per-token fitting, "
                    "so it can be computed once and shipped with the lens."))
    c2.html(ui.note("key", "Generalisable", "Built without the prompts of the task being read: at most a word, an "
                    "entry or a few examples per kind of situation, ideally nothing that names the task at all."))
    c3.html(ui.note("open", "As good as the family mean", "The family mean is the target. Each centre is scored by "
                    "the share of the family mean's gain it recovers, family by family."))
    ui.section("Where we are, family by family", "Strict pass rate on dev val (rms). Share = the centre's gain over "
               "the plain lens divided by the family mean's. Constant centres only; the same-token mean (not constant) "
               "is shown for reference.", eyebrow="Scoreboard")
    best = ["glos:word@self|rms", "glos:desc@self|rms", "genk:8@self|rms", "fam@plainothers|rms"]
    rows = []
    for f in screen.FAMILIES:
        t = screen.table(f, "val", tuple(["fam@fit|rms", "tok@fit|rms", *best]), S)
        if not t:
            continue
        z = screen.table(f, "val", ("zero|rms",), S).get("zero|rms")
        fam = t.get("fam@fit|rms")
        rows.append([f"<b>{f}</b>", rate(z), f"{rate(fam)} ({fmt_d(fam, False)})", rate(t.get('tok@fit|rms')),
                     *[f"{rate(t.get(a))} · {share(t.get(a), fam)}" for a in best]])
    ui.table(["family", "plain", "family mean (Δ)", "same-token", "glossary word · share", "glossary entry · share",
              "8 examples · share", "other tasks' bank · share"], rows, mono={1, 2, 3})
    st.html("<div class=\"jm-cap\">\"–\" share: the family mean's own gain is not reliably above 0 there (multihop, "
            "multilingual, and directed_modulation on strict; its judged results are in tab 5). Plain-family synthetic and glossary rows "
            "are being re-scored on regenerated references (notes/predictions.md).</div>")

# ================================================================== 2 · the means
with TABS[1]:
    ui.section("Every centre, by what it needs", "μ is subtracted from the state before the lens reads it. Grouped from "
               "most to least task data; within a group, the arm name in <code>code</code>.", eyebrow="The means")
    for tk, label, *_ in screen.TIERS:
        cs = [(a, c) for a, c in screen.CENTRES.items() if c["tier"] == tk]
        ui.label(f'<span style="color:{screen.TIER[tk][3] if ui.night() else screen.TIER[tk][2]}">●</span> {label}',
                 screen.TIER[tk][4])
        ui.table(["centre", "arm", "μ is", "varies by", "experiment"],
                 [[f"<b>{ui.esc(c['label'])}</b>", f"<code>{ui.esc(a)}</code>", ui.esc(c["blurb"]), ui.esc(c["constant"]),
                   ui.esc(c["exp"])] for a, c in cs])

    ui.section("The glossary, in full", "Each glossary centre is the mean state of texts the model wrote from one entry, "
               "never seeing a bank item. <b>word</b>: the word alone; <b>entry</b>: word + definition. Chat families add "
               "one format line (the same for word, entry and control) so a text can be read in their template.",
               eyebrow="Glossary")
    G = screen.glossary(S)
    H = [g for g in G if g["variant"] in ("word", "desc")]  # the hand-picked entries (x11 / x12)
    if H:
        G, G_all = H, G
        ui.table(["family", "word", "definition (entry variant)", "chat format line", "sets", "texts per set"],
                 [[f"<b>{f}</b>", f"<code>{ui.esc(next(g['word'] for g in G if g['family'] == f))}</code>",
                   ui.esc(next(g["definition"] for g in G if g["family"] == f)),
                   ui.esc(next((g["format"] for g in G if g["read_as"] == f and g["format"]), "–")),
                   ", ".join(sorted(g["variant"] + ("" if g["read_as"] == f else f" as {g['read_as']}") for g in G
                                    if g["family"] == f)),
                   ", ".join(str(g["n"]) for g in G if g["family"] == f)]
                  for f in screen.FAMILIES if any(g["family"] == f for g in G)])
        st.html('<div class="jm-cap">Control (<code>glosx:desc</code>): typo reads association\'s entry, association '
                "reads basic_readout's, basic_readout multihop's, multihop multilingual's, multilingual typo's; "
                "user_modeling and directed_modulation read each other's entry written in their own format.</div>")
        B = screen.blind(S)
        if B.get("entries"):
            ui.label("Blind entries (x13)", "the 27B wrote each entry from the first sentence of the family's README "
                     "in the bench, never seeing an item or a result")
            ui.table(["family", "README sentence it was given", "its word", "its definition"],
                     [[f"<b>{f}</b>", ui.esc(B["descriptions"].get(f, "")), f"<code>{ui.esc(e[0])}</code>", ui.esc(e[1])]
                      for f, e in B["entries"].items()])
        G = G_all  # every set, the blind (bword / bdesc) and no-entry (none) ones included, for reading the texts
        g1, g2 = st.columns([1.2, 1])
        pick = g1.selectbox("Read the texts of", [g["set"] for g in G], key="cm_gset",
                            format_func=lambda s: s.replace("glos-", "").replace("-", " · ", 1))
        g = next(x for x in G if x["set"] == pick)
        g2.html(f'<div class="cm-def" style="padding-top:28px"><b>{ui.esc(g["word"]) or "(no entry)"}</b>'
                + (f" — {ui.esc(g['definition'])}" if g["variant"] in ("desc", "bdesc") else "") + "</div>")
        ui.table(["#", "wikitext sentence" if g["source"] == "wikitext" else "text the model wrote"],
                 [[str(k + 1), ui.esc(t)] for k, t in enumerate(g["texts"])], num={0})
    else:
        st.info("No glossary reference sets in the store yet.")

    ui.section("Model-written prompts from examples", "For each item the model wrote prompts \"of exactly the same "
               "kind\" from that item's prompt (greedy, thinking off; generations reusing the prompt's last content word "
               "are dropped). <code>genk:k</code> averages the states of k OTHER items' texts; <code>gen</code> the "
               "item's own (the leak control).", eyebrow="Synthetic references")
    e1, e2 = st.columns([1, 1.6])
    wf = e1.selectbox("Family", screen.FAMILIES, key="cm_wf")
    wsplit = e1.segmented_control("Split", ["val", "fit"], default="val", key="cm_wsplit") or "val"
    W = screen.written(wf, wsplit, S)
    if W:
        bank = sources.bank(wf, wsplit)
        item = e2.selectbox(f"Item ({len(W)} with written prompts)", sorted(W), key=f"cm_witem_{wf}_{wsplit}",
                            format_func=lambda i: f"{i} · {', '.join(bank['targets'].get(i, [])[:2])}")
        spec = bank["specs"].get(item, {})
        src = spec.get("text") or next((m["content"] for m in reversed(spec.get("messages") or []) if m["role"] == "user"), "")
        st.html(f'<div class="cm-def"><b>The item</b> (target {ui.esc(", ".join(bank["targets"].get(item, [])))}): '
                f"{ui.esc(src)}</div>")
        ui.table(["#", "prompt the model wrote from it"], [[str(k + 1), ui.esc(t)] for k, t in enumerate(W[item])], num={0})
    else:
        st.info(f"The texts of {wf}/{wsplit}'s written prompts are not stored for this set yet (the plain-family sets "
                "are being regenerated with their texts recorded).")

    ui.section("The word dictionary", "Used by the one-word centres (x1-x3, x5, x7): μ = α · s<sub>l</sub> · "
               "v̂<sub>l</sub>(word), with v̂ the unit mean state at the word's last token over neutral carrier phrases, "
               "s<sub>l</sub> the typical ‖h‖, α = 0.5.", eyebrow="Words")
    D = screen.dictionary()
    if D:
        ui.table(["family", "family word (x2/x3)", "test name (x5)", "wrong word (control)", "stratum words (x2/x3/x7)"],
                 [[f"<b>{f}</b>", D["family_word"].get(f, "–"), D["family_word_v2"].get(f, "–"),
                   D["derangement"].get(f, "–"),
                   ", ".join(sorted(set(D.get("stratum_word", {}).get(f, {}).values()))) or "– (the family word)"]
                  for f in screen.FAMILIES], mono={1, 2, 3})
        st.html(f'<div class="jm-cap"><b>Full dictionary</b> ({len(D["dictionary"])} words, from which the 27B picked '
                f"per item for <code>dict:llm</code>): {', '.join(D['dictionary'])}. Neutral words (contrast "
                f"pool): {', '.join(D['neutral'])}.</div>")

# ================================================================== 3 · fit and test
with TABS[2]:
    ui.section("How each centre is fitted", "Every centre sees the read cell's position, token and preceding text, never "
               "its targets (the pipeline passes no targets to a centre). An item never contributes to its own μ.",
               eyebrow="Fitting")
    ui.table(["centre", "arm", "fitted on", "varies by"],
             [[ui.esc(c["label"]), f"<code>{ui.esc(a)}</code>", ui.esc(c["ref"]), ui.esc(c["constant"])]
              for a, c in screen.CENTRES.items()])
    ui.section("How each is tested", eyebrow="Testing")
    ui.prose(
        "<b>Splits.</b> Each family has a dev bank split in two, <code>fit</code> and <code>val</code>; the bench's own "
        "items are held out for final picks with the pinned judge. A centre named <code>@fit</code> is fitted on "
        "<code>fit</code> and tested on <code>val</code> (and on <code>fit</code> with the item left out); "
        "<code>@self</code> centres are built per bank from material that never includes the item's own prompt "
        "(except <code>gen</code>, the leak control).",
        "<b>Registration.</b> Each experiment (x1-x12) was written down with its predictions before its numbers were read "
        "(<code>notes/predictions.md</code>); outcomes are appended, never edited.",
        "<b>Reproducibility.</b> Every run is stamped with the branch and commit it ran on (provenance in each "
        "artefact); runs come from this branch merged with the latest <code>eval-pipeline</code>, and re-reads were "
        "checked identical cell by cell after each merge.",
        "<b>Screen, then judge.</b> All centres are screened with the free strict score on every family, fit and val. "
        "Where strict does not track the judge (user_modeling, directed_modulation) the promising ones are judged.")
    sizes = []
    for f in screen.FAMILIES:
        r = [len(sources.bank(f, s)["items"]) if (sources.DEV / f / f"{s}.json").exists() else "–" for s in ("fit", "val")]
        sizes.append([f, *map(str, r)])
    ui.table(["family", "fit items", "val items"], sizes, num={1, 2}, mono={0})

# ================================================================== 4 · evaluation
with TABS[3]:
    ui.section("Reading a cell", "The lens maps the (centred) state to scores over the whole vocabulary; we keep the top 10.",
               eyebrow="Evaluation")
    ui.eq(r"x = h_l - \mu_l, \qquad z = J_l\, x, \qquad s_{\mathrm{rms}}(t) = W_U[t] \cdot \Big( g \odot "
          r"\frac{z}{\sqrt{\mathrm{mean}(z^2) + \epsilon}} \Big)", tag="rms",
          note="the rms readout (the house readout): the model's own final norm (gain g) applied to J x, then the unembedding")
    ui.eq(r"s_{\cos}(t) = \frac{W_U[t] \cdot J_l\, x}{\lVert J_l^{\top} W_U[t] \rVert}", tag="cos",
          note="the bench's cosine readout (secondary here)")
    ui.eq(r"T(l, c) = \mathrm{top}_{10}\; s(t), \qquad l \in \{20, 24, \dots, 60\},\ c \in \text{read cells}", tag="top 10")
    ui.section("Scoring an item", eyebrow="Strict pass")
    ui.eq(r"\mathrm{pass}(i) = \mathbb{1}\Big[\, \exists\, l, c:\ T(l, c) \cap F(i) \neq \varnothing \,\Big]", tag="strict",
          note="F(i): the item's accepted target forms, each a whole token after dropping a leading space and casefolding "
               "(' Belgium' and 'belgium' count; ' Belg' does not)")
    ui.prose(
        "<b>Scored items.</b> jle's x89 rule: items whose target already appears in the prompt as a token (leak) and items "
        "with no single-token target (unreachable) are excluded; the rest are scored.",
        "<b>Pass rate</b> of a centre on a bank = the share of scored items that pass. <b>Δ</b> = its pass rate minus the "
        "plain lens's on the same items (paired). <b>95 % interval</b>: 10,000 bootstrap resamples of the items, the "
        "same resample for both arms. A Δ is coloured when its interval excludes 0.",
        "<b>Share of the family mean</b> = Δ(centre) / Δ(family mean), shown where the family mean gains more than 0.02.",
        "<b>Judged tier</b> (user_modeling, directed_modulation): Haiku 5.5 (development judge, unpinned) reads each "
        "read cell's top tokens with the bench's own judge prompt at layers 24, 36, 48 and 60; a directed_modulation "
        "item passes when at some judged cell the judge picks the held concept as content (content-bound), not as an "
        "echo of the prompt.",
        "<b>Controls</b> recorded for every arm: the prompt-masked readout (prompt-content tokens removed before the top "
        "10), echo (share of the top 10 that are the prompt's own content words), and overlap with the model's own next "
        "token.")

# ================================================================== 5 · families and results
with TABS[4]:
    ui.section("The seven WorkspaceBench families", "What each asks, where the lens reads it, what counts as a hit, an "
               "example from the dev bank, and every centre's result.", eyebrow="Families")
    fam = st.segmented_control("Family", screen.FAMILIES, default="typo", key="cm_fam") or "typo"
    what, where, hit = screen.FAMILY_DOC[fam]
    bank = sources.bank(fam, "val")
    ex_id = next(iter(bank["items"]))
    sp = bank["specs"].get(ex_id, {})
    ex_text = sp.get("text") or "  ".join(f"[{m['role']}] {m['content']}" for m in sp.get("messages") or [])
    l, r = st.columns([1, 1.2], gap="large")
    l.html(f'<dl class="jm-spec facts"><dt>asks</dt><dd>{ui.esc(what)}</dd><dt>read at</dt><dd>{ui.esc(where)}</dd>'
           f"<dt>a hit is</dt><dd>{ui.esc(hit)}</dd><dt>subfamilies</dt><dd>"
           f"{ui.esc(', '.join(sorted({i.get('subfamily') for i in bank['items'].values() if i.get('subfamily')})) or '–')}"
           f"</dd></dl>")
    r.html(f'<div class="cm-def"><b>Example</b> <code>{ui.esc(ex_id)}</code><br>{ui.esc(ex_text)}<br>'
           f"<b>targets</b>: {ui.esc(', '.join(bank['targets'].get(ex_id, [])))}</div>")

    names = tuple(screen.arms(fam, "val", "rms"))
    tv, tf = screen.table(fam, "val", names, S), screen.table(fam, "fit", tuple(screen.arms(fam, "fit", "rms")), S)
    J = screen.judged(fam, "val", names, S) if fam in screen.CHAT else {}
    head = ["group", "centre", "val", "Δ val [95 %]", "fit", "Δ fit"] + (["judged val"] if J else [])
    body = []
    for a in order({*tv, *tf}):
        tier, label, _ = screen.info(a)
        row = [f'<span style="color:{screen.colour(a)}">●</span> {ui.esc(tier[1])}', ui.esc(label), rate(tv.get(a)),
               fmt_d(tv.get(a)), rate(tf.get(a)), fmt_d(tf.get(a), False)]
        if J:
            j = J.get(a)
            row.append("–" if not j else f"{j['value']:.2f} [{j['ci'][0]:.2f}, {j['ci'][1]:.2f}]")
        body.append(row)
    ui.label(f"{fam} · strict, rms", f"val n = {next(iter(tv.values()))['n'] if tv else '–'} · Δ against the plain lens")
    ui.table(head, body, mono={2, 4})
    if tv:
        pts = [(a, tv[a]) for a in order(tv) if a != screen.PLAIN]
        fig = go.Figure()
        for a, q in pts:
            lab = screen.info(a)[1]
            fig.add_trace(go.Scatter(x=q["ci"], y=[lab, lab], mode="lines", line=dict(color=screen.colour(a), width=3),
                                     opacity=0.4, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=[q["diff"]], y=[lab], mode="markers", marker=dict(size=10, color=screen.colour(a)),
                                     hovertemplate=f"<b>{ui.esc(lab)}</b><br>rate {q['rate']:.2f} · Δ {q['diff']:+.2f}"
                                                   f" [{q['ci'][0]:+.2f}, {q['ci'][1]:+.2f}]<extra></extra>"))
        fig.add_vline(x=0, line=dict(color=ui.c("h"), width=1.5))
        if "fam@fit|rms" in tv:
            fig.add_vline(x=tv["fam@fit|rms"]["diff"], line=dict(color=ui.c("delta"), dash="dash", width=1.5))
        ui.plot_layout(fig, 60 + 24 * len(pts))
        fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=[screen.info(a)[1] for a, _ in pts])
        fig.update_xaxes(title=dict(text=f"Δ strict pass vs plain, {fam} val (dashed: family mean)", font=dict(size=12)))
        ui.chart(fig, f"cm_fam_{fam}")
    if fam == "user_modeling":
        st.html('<div class="jm-cap">user_modeling pass@10 cannot separate user modelling from reading the prompt '
                "(iteration S11): the lens surfaces the attribute even when the sentence is quoted about someone else. "
                "These numbers screen; they are not evidence.</div>")
    if fam == "directed_modulation":
        st.html('<div class="jm-cap">Strict is near the floor here; the judged column is the result of record. The '
                "same-token mean's gain is partly the same-sentence leak on these dev banks (fit and val share "
                "carrier sentences); iteration's fair versions reach 0.57-0.64 judged.</div>")

# ================================================================== 6 · every item
def chip_list(r: dict | None, forms: set, family: str) -> str:
    """One version's top 10 at a cell as chips (accepted targets outlined), with the layer (and read token) above."""
    if not r:
        return '<span class="cm-mut">no readout</span>'
    cs = "".join(f'<span class="cm-chip{" hit" if sources.is_hit(family, t, forms) else ""}">'
                 f'{html.escape(sources.decode_token(t).replace(chr(10), "↵") or "∅")}</span>' for t in r["tokens"])
    where = f'L{r["layer"]}' + (f' · “{html.escape(sources.decode_token(r["token"]).strip())}”' if family in screen.CHAT else "")
    rank = f' · target #{r["rank"] + 1}' if r.get("rank") is not None else ""
    return f'<div class="cm-mut" style="font-size:11px">{where}{rank}</div>{cs}'


def prompt_of(B: dict, i: str, cut: int = 0) -> str:
    sp = B["specs"].get(i, {})
    t = sp.get("text") or next((m["content"] for m in reversed(sp.get("messages") or []) if m["role"] == "user"), "")
    return html.escape(t if not cut or len(t) <= cut else t[: cut - 1] + "…")


with TABS[5]:
    ui.section("Every tested sentence, top 10 per reader and centre", "Pick a sentence to see it read by every version at "
               "once (each reader in the store: J-lens, J++ lens, logit lens; each centre), or scan a whole bank for a few "
               "chosen versions. Top 10 at the chosen layer, or at each version's best layer (where it ranks the target "
               "best). Accepted targets are outlined. For the chat families the read cell shown is the one where that "
               "version ranks the target best; hover every cell on Passage → readouts.", eyebrow="Items")
    st.html("""<style>
    .cm-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:8px; margin:4px 0 14px; }
    .cm-card { background:var(--surface); border:1px solid var(--line); border-top:3px solid var(--c); border-radius:8px;
               padding:6px 8px; min-width:0; }
    .cm-card .nm { font-weight:600; font-size:12.5px; color:var(--ink); margin-bottom:2px; }
    .cm-card.hitc { box-shadow: inset 0 0 0 1px var(--delta); }
    </style>""")
    view = st.segmented_control("View", ["One sentence, every version", "Every sentence, chosen versions"],
                                default="One sentence, every version", key="cm_iview") or "One sentence, every version"
    i1, i2, i3 = st.columns([1.1, 0.7, 1.2], vertical_alignment="bottom")
    ifam = i1.selectbox("Family", screen.FAMILIES, key="cm_ifam")
    isplit = i2.segmented_control("Split", ["val", "fit"], default="val", key="cm_isplit") or "val"
    avail = screen.reader_arms(ifam, isplit)
    B = sources.bank(ifam, isplit)
    scored = B["scored"] or set(B["items"])
    ids = [i for i in B["items"] if i in scored]
    first = avail[0] if avail else None
    layers = sorted({L for (_, L, _) in sources.cells(ifam, isplit, sources.arm_dir(first),
                                                      sources.readouts_mtime(ifam, isplit, sources.arm_dir(first)))}) if first else []
    lay = i3.selectbox("Layer", ["best per version", *layers], key="cm_ilayer",
                       format_func=lambda L: L if isinstance(L, str) else f"L{L}")
    L = None if isinstance(lay, str) else lay

    def tops_of(a: str) -> dict:
        return screen.tops(ifam, isplit, a, L, sources.readouts_mtime(ifam, isplit, sources.arm_dir(a)))

    if not avail or not ids:
        st.info("No readouts for this bank yet.")
    elif view == "One sentence, every version":
        key_item = f"cm_isent_{ifam}_{isplit}"
        if st.session_state.get(key_item) not in ids:
            st.session_state[key_item] = ids[0]

        def step(d: int) -> None:
            st.session_state[key_item] = ids[(ids.index(st.session_state[key_item]) + d) % len(ids)]

        s1, s2, s3, s4 = st.columns([10, 1, 1, 3], vertical_alignment="bottom")
        item = s1.selectbox(f"Sentence · {len(ids)} scored", ids, key=key_item,
                            format_func=lambda i: f"{i} · {prompt_of(B, i, 90)} → {', '.join(B['targets'].get(i, [])[:2])}")
        s2.button("", icon=":material/arrow_back:", on_click=step, args=(-1,), key="cm_iprev", width="stretch")
        s3.button("", icon=":material/arrow_forward:", on_click=step, args=(1,), key="cm_inext", width="stretch")
        readers = s4.multiselect("Readers", list(screen.LENS_NAMES), default=list(screen.LENS_NAMES), key="cm_ireaders",
                                 format_func=lambda r: screen.LENS_NAMES[r].split(" (")[0])
        forms = set(B["forms"].get(item, []))
        st.html(f'<div class="cm-def" style="font-size:15px;margin:6px 0 10px"><b>{prompt_of(B, item)}</b><br>'
                f'targets: <b>{ui.esc(", ".join(B["targets"].get(item, [])))}</b> · '
                f'{ui.esc(screen.FAMILY_DOC[ifam][1])}</div>')
        for reader in readers:
            group = [a for a in avail if catalog.parse(a).lens == reader]
            if not group:
                continue
            cards, n_hit = [], 0
            for a in group:
                r = tops_of(a).get(item)
                hit = bool(r) and any(sources.is_hit(ifam, t, forms) for t in r["tokens"])
                n_hit += hit
                base = a.split(":", 1)[1] if reader != "jlens" else a
                cards.append(f'<div class="cm-card{" hitc" if hit else ""}" style="--c:{screen.colour(base)}">'
                             f'<div class="nm">{ui.esc(screen.info(base)[1])}</div>{chip_list(r, forms, ifam)}</div>')
            ui.label(screen.LENS_NAMES[reader], f"{len(group)} centres · target in the top 10 for {n_hit}")
            st.html('<div class="cm-grid">' + "".join(cards) + "</div>")
    else:
        default = [a for a in ("zero|rms", "fam@fit|rms", "glos:word@self|rms", "jpp:zero|rms", "jpp:fam@fit|rms") if a in avail]
        chosen = st.multiselect("Reader · centre", avail, default=default, key=f"cm_iarms_{ifam}_{isplit}",
                                format_func=screen.label)
        T = {a: tops_of(a) for a in chosen}
        st.caption(f"{len(ids)} scored sentences · {len(chosen)} readers × centres")
        th = "".join(f'<th class="cm-c"><span style="color:{screen.colour(a)}">●</span> {ui.esc(screen.label(a))}</th>'
                     for a in chosen)
        tb = "".join(f'<tr><td style="min-width:240px"><code>{ui.esc(i)}</code><br>{prompt_of(B, i, 220)}<br>'
                     f'<b>{ui.esc(", ".join(B["targets"].get(i, [])))}</b></td>'
                     + "".join(f'<td class="cm-c">{chip_list(T[a].get(i), set(B["forms"].get(i, [])), ifam)}</td>' for a in chosen)
                     + "</tr>" for i in ids)
        st.html(f'<div class="jm-wrap" style="max-height:900px;overflow:auto"><table class="jm-table cm-tbl"><thead><tr>'
                f"<th>sentence</th>{th}</tr></thead><tbody>{tb}</tbody></table></div>")

# ================================================================== 7 · versus other techniques
with TABS[6]:
    ui.section("The same families read by other techniques", "Every reader and centre the shared store holds for these "
               "banks, against the plain J-lens on the same items (strict, val, rms). Other readers: the J++ lens "
               "(Ayonrinde & Lindsey 2026) and the logit lens (no map: the state read straight through the final norm and "
               "unembedding), plain and with the same centres. Other centring techniques: the studies on the "
               "<code>iteration</code> branch, as their results reach the store.", eyebrow="Comparison")
    keep = ["zero|rms", "fam@fit|rms", "tok@fit|rms", "glos:word@self|rms", "genk:8@self|rms", "fam@plainothers|rms"]
    grid: dict[tuple, dict[str, dict]] = {}
    for f in screen.FAMILIES:
        names = tuple(dict.fromkeys(keep + screen.others(f, "val")))
        for a, q in screen.table(f, "val", names, S).items():
            arm = catalog.parse(a)
            base = a.split(":", 1)[1] if arm.lens != "jlens" else a  # the centre part, without the reader prefix
            ours = base.split("|")[0] in screen.CENTRES
            kind = "this study" if arm.lens == "jlens" and ours else "other reader" if arm.lens != "jlens" else "other study"
            key = ({"this study": 0, "other reader": 1, "other study": 2}[kind], list(screen.LENS_NAMES).index(arm.lens)
                   if arm.lens in screen.LENS_NAMES else 9, keep.index(base) if base in keep else 99, kind,
                   screen.LENS_NAMES.get(arm.lens, arm.lens), screen.info(base)[1] if ours else arm.centre)
            grid.setdefault(key, {})[f] = q
    fams = [f for f in screen.FAMILIES if any(f in v for v in grid.values())]
    rows = [[k[3], f"<b>{ui.esc(k[4])}</b>", ui.esc(k[5]),
             *[f"{v[f]['rate']:.2f} <span style=\"font-size:11px\">{fmt_d(v[f], False)}</span>" if f in v else "–"
               for f in fams]] for k, v in sorted(grid.items())]
    ui.label("Pass rate (Δ vs the plain J-lens on the same items)", "strict · val · rms")
    ui.table(["source", "reader", "centre", *fams], rows, mono=set(range(3, 3 + len(fams))))
    st.html('<div class="jm-cap">Not run here: readers that need new model passes (natural-language autoencoders, '
            "oracle or patching readouts). The J++ and logit-lens rows for the synthetic and glossary centres follow the "
            "reference regeneration; other studies' centres appear as their branches push results.</div>")
