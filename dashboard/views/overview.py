"""Setup: the question, how one cell is read, what mu must satisfy, fixed settings, repo map, progress."""

import streamlit as st

import figures
import sources
import ui

stamp = sources.stamp()
ex = sources.examples(stamp)

ui.header(
    "Research question",
    'How should we choose <span class="m c-mu">μ<sub>l</sub></span> in the centred J-lens readout?',
    'The Jacobian lens reads a residual-stream state <span class="m c-h">h<sub>l</sub></span> by mapping it to the final '
    'layer with a fixed matrix <span class="m">J<sub>l</sub></span>. Subtracting a centre <span class="m c-mu">μ<sub>l</sub></span> '
    'first makes it read far better. This project asks what <span class="m c-mu">μ<sub>l</sub></span> should be, when it may '
    'depend on <span class="m c-h">h<sub>l</sub></span> and on the context of the read, without leaking the answer into the readout.',
)
st.write("")
ui.figure(figures.formula())

ui.section("From a residual to ten tokens", eyebrow="How one cell is read")
if ex:
    ui.figure(
        figures.readout_path(ex[0]["fam"], ex[0]["target"]),
        "<b>One read cell.</b> The residual at block <i>l</i> and one token position (blue) is centred, carried to the last "
        "layer by the fixed lens <i>J<sub>l</sub></i>, scored against the vocabulary and cut to a top-10 bag. Both readouts "
        "are linear in <i>h</i>, so a centred read is the plain read minus the read of <i>μ</i>. The tokens shown are the "
        f"real centred readout of <code>{ex[0]['id']}</code> at L{ex[0]['layer']} (“{ui.esc(ex[0]['prompt'])}”).",
    )

ui.section('What a good <span class="m c-mu">μ</span> has to be', eyebrow="From the brief")
st.html('<div class="jm-props">' + "".join(
    f'<div><h4>{t}</h4><p>{b}</p><span class="q">{q}</span></div>' for t, b, q in [
        ("Generalisable", "Works across WorkspaceBench families and on free text, where no template fixes the read cell.",
         "one μ per layer fails here"),
        ("Cheap", "A mean of a few reference states, not a refit of the lens. Eight reference prompts already suffice for a "
         "family mean.", "bootstrap SD &lt; 0.01"),
        ("Fair", "Never sees the targets, and never subtracts or re-reads the prompt so that a mention looks like a thought.",
         "the mention control"),
        ("Principled", "Has a reason to work: a stated counterfactual <i>E[h | C]</i>, not a tuned offset.",
         "μ is a counterfactual"),
    ]) + "</div>")

ui.section("Setup", eyebrow="Fixed for every arm")
st.html('<dl class="jm-spec">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in [
    ("Model", "Qwen3.6-27B (64 blocks, d = 5120, vocabulary 248k). Forward passes on RunPod; everything after capture runs on the Mac."),
    ("Lens", "The released J-lens only: <code>neuronpedia/jacobian-lens</code> n1000 (wikitext), pinned <code>a4114d7</code>. "
     "Never refit, never J++. It reads <i>J h</i>, which has no centre."),
    ("Layers", "11 read layers, L20 to L60 in steps of 4. An item passes if any layer passes."),
    ("Readouts", "<code>cos</code>, the bench's, and <code>rms</code>, jle's. They differ by up to 0.09 uncentred and agree "
     "within 0.033 after centring."),
    ("Families", "The seven WorkspaceBench single-token families: typo, association, basic_readout, multihop, "
     "multilingual, user_modeling and directed_modulation, each with dev <code>fit</code> / <code>val</code> banks and "
     "the bench. Plus four multi-token families, kept separate: typo_mt, multihop_mt, basic_readout_mt and "
     "multilingual_mt, with new dev banks gated on the 27B (multilingual_multihop and multilingual_typo come later)."),
    ("Centres", "<code>zero</code> (the plain lens), <code>fam</code> (one mean per layer over the family) and "
     "<code>tok</code> (mean over cells with the same read token), each fitted leave-one-out or on the held-out "
     "<code>fit</code> split. The item's own group is always excluded (on DM, its twin)."),
    ("Scoring", "Free strict match (a whole top-10 token equals a target) plus the full-vocabulary target rank, on all "
     "seven families. The LLM judge (Haiku 5.5 for development) on dev <code>val</code>. Strict tracks the judge on five "
     "families; on user_modeling and directed_modulation only judged numbers rank centres. On the multi-token families "
     "the free score is a distinctive-piece proxy (a rough guide, item κ 0.2–0.7) and the judge (the bench's summarizer "
     "+ regex, about $0.07 per val arm) ranks centres."),
]) + "</dl>")

ui.section("Two lineages, one pipeline", "The prior centring work came in as two self-contained subtrees. New work sits at "
           "the top level and imports from both.", eyebrow="Where the code lives")
ui.figure(figures.repo_map())

ui.section("Where each family stands", "Read from <code>data/dev</code>, <code>out/captures</code> and <code>out/eval</code> "
           "on load. The typo bench is scored from umot's existing bf16 bench captures, read in place. The pipeline is "
           "complete for all seven single-token families and the four multi-token ones; next is screening new centres.",
           eyebrow="Progress")
B, R, A = sources.banks(stamp), sources.results(stamp), sources.agreement(stamp)
rows = []
for f in sources.ALL_FAMILIES:
    b = B[f]
    sz, cap = b["sizes"], b["captured"]
    ncap = sum(cap.values()) + (f == "typo" and "bench" in R.get(f, {}))  # typo bench: umot's captures
    nev = len(R.get(f, {}))
    narms = len(sources.arm_dirs(f, "val"))
    njudged = sum(bool(sources.judge_runs(f, "val", d)) for d in sources.arm_dirs(f, "val"))
    rows.append([f, " / ".join(str(sz.get(s, "–")) for s in sources.SPLITS),
                 ui.pill("done" if sz.get("fit") else "todo"),
                 ui.pill("done" if ncap >= 3 else "part" if ncap else "todo"),
                 ui.pill("done" if nev == 3 else "part" if nev else "todo") + f' <span class="jm-n">{narms} arms</span>',
                 ui.pill("done" if njudged else "todo") + (f' <span class="jm-n">{njudged} arm{"s" if njudged > 1 else ""}</span>' if njudged else ""),
                 "piece proxy: rank by judge" if f in sources.MT_FAMILIES else
                 "yes" if f in sources.STRICT_IS_PROXY else '<span style="color:var(--warn)">no: rank by judge</span>'])
ui.table(["family", "items fit / val / bench", "dev bank", "captured", "evaluated", "judged (val)", "strict as proxy"],
         rows, num={1}, mono={0})
