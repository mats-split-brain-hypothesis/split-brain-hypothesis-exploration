"""How the pipeline works: stages, arm names, what g may see, the g interface, controls, the research cycle, commands,
parallel instances, and what is built and owed. Sources: notes/eval-pipeline.md and notes/iteration-anthony/research-loop.md."""

import streamlit as st

import figures
import ui


def W(html: str) -> str:
    """A table cell that may wrap (ui.table cells stay on one line)."""
    return f'<span class="wrap">{html}</span>'

ui.header(
    "Shared evaluation pipeline · src/jlm",
    'One harness for every candidate <span class="m c-mu">g</span>',
    'Any readout of the form <span class="m">J<sub>l</sub>(h<sub>l</sub> − <span class="c-mu">g</span>)</span> plugs in: '
    '<span class="m c-mu">g</span> may be a mean, a function of the state itself, of earlier positions or of reference '
    "text, as long as it never sees the answer. The 27B runs once per bank on a pod; every arm is then read, scored, "
    "controlled and analysed from the stored residuals against the same banks, splits and judges.",
)

ui.section("From a bank to a verdict", eyebrow="Stages")
ui.figure(figures.stages(), "<b>Three places.</b> Only the two captures need the 27B. Everything a new <i>g</i> needs runs "
          "from the stored residuals with W<sub>U</sub>, the final norm and the lens: on a pod GPU by default (a few minutes "
          "for every family), on the Mac when it is free. Pods share one network volume, so the model, captures and "
          "results are downloaded or computed once. The judge is the only per-call spend; it runs on <code>val</code> "
          "(and on the bench for finalists).")

ui.section("An arm is a centre, a reference split and a readout", eyebrow="Naming")
left, right = st.columns([1.3, 1], gap="large")
with left:
    ui.figure(figures.arm_grammar(), "<b><code>fam@self</code> is jle's leave-one-out mean (loo1); <code>fam@fit</code> read "
              "on val or bench is its held-out dev mean (dev1).</b> Bench parity with jle x100 holds for all five "
              "families, to within one item. Directories swap the symbols: <code>fam-at-fit__cos</code>.")
with right:
    ui.label("Prefixes", "same arm, one thing changed")
    ui.table(["prefix", "example", "what it changes"], [
        ["<code>shuf.</code>", "<code>shuf.tok@fit|cos</code>",
         W("control: each cell is read with another cell's <i>g</i> (same layer, seeded cycle)")],
        ["<code>rand.</code>", "<code>rand.fam@fit|cos</code>",
         W("control: a random direction with each cell's ‖<i>g</i>‖")],
        ["<code>jpp:</code>", "<code>jpp:zero|cos</code>",
         W("reads through the J++ lens: a comparison map, never a centre's lens (dir <code>jpp~zero__cos</code>)")],
        ["study name", "<code>mycentre@fit|cos</code>",
         W("a centre from <code>src/jlm/mu/&lt;study&gt;.py</code>, registered on import")],
    ])

ui.section("Splits, and what g is allowed to see", eyebrow="Discipline")
left, right = st.columns(2, gap="large")
with left:
    ui.figure(figures.splits(), "<b>Fit chooses, val confirms, bench records.</b> Dev banks are jle's bank v2 split in two, "
              "plus new banks for directed_modulation and the four multi-token families. No dev item shares a target "
              "with the bench (except user_modeling, whose targets are closed sets like male / female), and no dev "
              "prompt reuses a bench prompt. When val has been read too often, a new dev split is authored.", narrow=True)
with right:
    ui.figure(figures.cellref(), "<b>The “no crystal ball” rule is enforced by the interface.</b> A centre gets a "
              "<code>CellRef</code> (or a <code>Batch</code> of them with their states), never targets. The item's whole "
              "group is left out of its reference set: on directed_modulation the group is the pair, whose twin holds "
              "the same concept.", narrow=True)

ui.section('Writing a <span class="m c-mu">g</span>', "Two forms; the pipeline picks whichever the class has "
           "(<code>centres.apply</code>).", eyebrow="Interface")
c1, c2, c3 = st.columns(3, gap="large")
c1.html(ui.note("key", "A vector per cell: <code>__call__(CellRef) → μ</code>",
                "For any mean over matching reference cells, subclass <code>KeyedMean</code> and give a "
                "<code>key(cell)</code>: <code>FamilyMean</code> keys on nothing, <code>TokenMean</code> on the read "
                "token (falling back to the family mean). <code>support(cell)</code> reports how many cells are behind "
                "μ, which the Centres page shows."))
c2.html(ui.note("key", "A map of the state: <code>transform(Batch) → h − g</code>",
                "For <i>g</i> that depends on <i>h</i>, other layers or earlier positions: projections, shrinkage, "
                "kNN means, cross-layer transport. A <code>Batch</code> holds one layer's cells, their states, the "
                "bank's read-cell captures and, with <code>needs_ctx</code>, the every-position context store. The "
                "<code>shuf.</code> and <code>rand.</code> controls are transforms too."))
c3.html(ui.note("open", "Where it lives",
                "Study centres go in <code>src/jlm/mu/&lt;study&gt;.py</code> and register themselves in "
                "<code>CENTRES</code> on import, so parallel instances never edit the same file. Add a test in "
                "<code>tests/test_jlm.py</code>. On this dashboard nothing is required: one line in "
                "<code>catalog.py</code> gives the arm a label and colour."))

ui.section("Controls in every run", "The failure we fear most is a g that scores by surfacing the prompt or the model's "
           "own next-token guess. A gain that vanishes under a control does not count toward the headline.",
           eyebrow="Controls")
ui.table(["control", "question it answers", "how", "status"], [[r[0], W(r[1]), W(r[2]), r[3]] for r in [
    ["prompt echo", "is the top 10 full of prompt words?", "share of top-10 tokens that are the item's prompt-content "
     "forms (template words excluded)", ui.pill("done") + ' <span class="jm-n">every arm</span>'],
    ["prompt-masked pass@10", "does the gain survive without prompt tokens?", "re-rank with every prompt form removed "
     "from the vocabulary (<code>masked.jsonl</code>), re-score", ui.pill("done") + ' <span class="jm-n">every arm</span>'],
    ["next-token baseline", "is it the model's own next-token output?", "overlap with the 27B's top 10 at the cell "
     "(final layer of the context capture)", ui.pill("part") + ' <span class="jm-n">needs ctx capture</span>'],
    ["shuffled g", "is it this cell's g, or any g of this kind?", "<code>shuf.</code> prefix", ui.pill("done")],
    ["random g", "is it a norm or bias effect?", "<code>rand.</code> prefix", ui.pill("done")],
    ["reference arms", "better than what we have?", "<code>zero</code>, <code>fam@fit</code>, <code>tok@fit</code> "
     "in every report", ui.pill("done")],
    ["per-category", "risks specific to the kind of g", "named on the idea card: mention control, random subspace, "
     "scrambled context, a rewrite that keeps the content…", '<span class="jm-n">per study</span>'],
]])

ui.section("The research cycle", "From notes/iteration-anthony/research-loop.md, agreed with the user on 2026-10-10. Ideas and results "
           "live in notes/iteration-anthony/mu-log.md and notes/iteration-anthony/studies/&lt;id&gt;.md.", eyebrow="Process")
left, right = st.columns([1.2, 1], gap="large")
left.html("""<ol class="jm-steps">
<li><b>Ideate.</b> An idea card in <code>notes/iteration-anthony/mu-log.md</code>: the counterfactual <i>g</i> stands for, the mechanism,
cost, fairness risk, its controls and a prediction, all written before the run.</li>
<li><b>Screen on <code>fit</code>.</b> Read with <code>@self</code> (leave-one-group-out), strict / piece proxy, all eleven
families, on the pod GPU. Hyperparameters are chosen here and only here.</li>
<li><b>Confirm on <code>val</code>.</b> Read with <code>@fit</code>, strict plus Haiku 5.5. The judge is mandatory on
user_modeling, directed_modulation and the <code>_mt</code> families, where strict is not a proxy.</li>
<li><b>Analyse.</b> <code>experiments/analyse.py</code>: paired gains and won / lost items, per-layer curves, rank
moves, what <i>g</i> removes, the controls, slices. Then a deep dive on the readouts; each insight points to the next
card.</li>
<li><b>Bench, finalists only.</b> After a registration in jle's style, with the pinned Gemini judge. The bench is
never used to choose.</li>
</ol>""")
right.html(ui.note("key", "Headline", "Pass@10 under the bench's item rule. The <b>macro-average over families</b> of the "
                   "gain against <code>fam@fit|cos</code> (and <code>tok@fit|cos</code> where it is better), with a "
                   "<b>no-harm guardrail</b>: no family drops outside its paired bootstrap interval. basic_readout and "
                   "multilingual sit near ceiling and act mostly as guardrails. Single-family studies are fine, with "
                   "the guardrail run on the rest.")
           + '<div style="height:14px"></div>'
           + ui.note("open", "Rules that do not bend", "No crystal ball: <i>g</i> never sees the item's targets. No "
                     "degenerate <i>g</i>: specified before it sees a val item, few hyperparameters, a stated mechanism. "
                     "A <i>g</i> that reads or subtracts the prompt does not count, however high it scores. Released "
                     "lenses only. Haiku numbers are unpinned dev numbers, never WorkspaceBench scores."))

ui.section("Commands", eyebrow="How to run")
st.code(
    """# pods: one shared volume (jlm-shared, US-MO-1); the instance that creates a pod terminates it
INSTANCE=j-lens-mean-f3 STUDY=S1 GPU=eval bash tools/pod.sh create s1    # GPU=capture for the 27B (80 GB)
bash tools/pod.sh setup s1                                              # ship HEAD, uv sync, out/ -> /workspace/out
BANKS=F/fit,F/val,F/bench bash tools/capture_pod.sh                      # pod: read-cell residuals (capture.py per bank)
python experiments/capture_ctx.py --banks all                           # pod: every position (+ --corpus wikitext)
python experiments/evaluate.py --banks F/fit --arms "zero|cos,mine@self|cos,shuf.mine@self|cos,rand.mine@self|cos" --device cuda
python experiments/judge.py --family F --split val --arms "mine@fit|cos" [--layers 24,36,48,60]   # Haiku 5.5
python experiments/analyse.py --study S1 --split val --arms "mine@fit|cos" [--decode-g]
python experiments/report.py --split val                                # one table across families
bash tools/sync.sh down s1 eval analysis                                # volume -> Mac (never deletes)
bash tools/pod.sh terminate s1                                          # logs the pod's cost to the ledger""",
    language="bash",
)

ui.section("Several instances at once", "Claude instances may iterate overnight in parallel; most compute is on RunPod.",
           eyebrow="Coordination")
c1, c2, c3 = st.columns(3, gap="large")
c1.html(ui.note("key", "Budget", "<b>$30 per overnight session, shared by every instance</b>, covering pods and the judge. "
                "Each paid step is logged (<code>tools/board.py spend</code>) and checked against the cap first "
                "(<code>board.py check 2.50</code>). Ask the user before any single judge run over about $5."))
c2.html(ui.note("key", "Board and messages", "<code>~/.jlm/board.tsv</code>: one line per instance (study, status, Mac "
                "job peak, pod), read with <code>board.py show</code> before claiming a card or starting a job. "
                "Messages only for claims, findings that affect another study, and requests to yield."))
c3.html(ui.note("key", "Mac memory and git", "16 GB, shared with the user's apps: at most one heavy job "
                "(<code>~/.jlm/mac.lock</code>, 5-7 GB per eval), and the pod is the default. Each instance works in "
                "its own worktree, commits to <code>iteration</code>, and flags pipeline changes "
                "“[pipeline candidate]”."))

ui.section("Where it stands", "As of 2026-10-10.", eyebrow="Status")
left, right = st.columns(2, gap="large")
with left:
    ui.label("Built")
    st.html("""<ol class="jm-steps">
<li><b>Eleven families end to end.</b> Seven single-token and four multi-token: dev banks, captures of fit / val /
bench, <code>zero</code> and <code>fam</code> (plus <code>tok</code> on user_modeling, DM and the <code>_mt</code>
families) evaluated, <code>val</code> judged with Haiku, strict-vs-judge agreement measured.</li>
<li><b>The loop's infrastructure.</b> The <code>transform(Batch)</code> interface and study modules, the
<code>shuf.</code> / <code>rand.</code> controls, prompt echo and the masked readout in every evaluation, the analysis
battery (smoke-tested on four banks), J++ comparison arms, the context-capture store, and the pod, sync and board
tools.</li>
<li><b>The Loop pages.</b> Leaderboard, Means / g compared and a generic Studies page, all generated from
<code>out/eval</code> and <code>out/analysis</code>.</li>
</ol>""")
with right:
    ui.label("Owed")
    st.html("""<ol class="jm-steps">
<li><b>Context captures.</b> The code is in; no every-position capture or wikitext corpus has reached the Mac yet.
They unblock the next-token control and every <i>g</i> that looks beyond the read cell.</li>
<li><b>The first study.</b> Every card in the backlog (S1–S9, U1–U2) is still an idea. S1 (random <i>g</i>) is the
cheapest first run.</li>
<li><b><code>tok</code> on the five proxy families</b>, and dev banks for multilingual_multihop and
multilingual_typo.</li>
<li><b>The pinned judge.</b> Only smoke-tested (33 calls); Haiku–Gemini agreement unmeasured; no registration
written yet.</li>
</ol>""")
