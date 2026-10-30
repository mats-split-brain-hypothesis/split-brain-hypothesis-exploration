"""Names, colours and descriptions for the pipeline's arms. An arm is ``centre@ref|readout`` (``zero|cos`` has
no ref); its readouts live in ``out/eval/<family>/<split>/<centre>-at-<ref>__<readout>/``.

To add a centring: run ``experiments/evaluate.py`` with the new arm; it appears on the explorer as soon as its
directory exists. Then add one ``CENTRES`` entry below to give it a name, a colour and a sentence. A centre with
no entry still shows, under its raw name and a colour derived from it.

A control is a prefix on the centre (``shuf.tok@fit|cos``: each cell read with another cell's g; ``rand.fam@fit|cos``:
a random direction with the cell's ||g||). Its label and colour derive from the inner centre's ("Shuffled g · Same read
token", a lighter shade, dashed lines), so controls need no entry. A study centre with no entry (``jlm.mu``) shows
under its raw name, a colour hashed from it, and its class's ``doc`` as the blurb.

Another map is an arm prefix: ``jpp:zero|cos`` reads through the J++ lens (directory ``jpp~zero__cos``). Its arms
take the label suffix and colours from ``LENSES``; everything else keys on the centre.
"""

import hashlib
from dataclasses import dataclass
from functools import lru_cache

import ui


@dataclass(frozen=True)
class Centre:
    label: str
    light: str  # identity colour on the light theme
    dark: str  # the same hue stepped for the dark theme
    blurb: str  # what mu is, in one sentence
    order: int = 50


CENTRES = {
    "zero": Centre("Plain J-lens", "#3b63c9", "#6b8de6", "No centre: μ = 0, the released lens.", 0),
    "fam": Centre("Family mean", "#0f8a77", "#22a085", "One μ per layer: the mean state over the family's read cells.", 10),
    "tok": Centre("Same read token", "#b9781a", "#c98a2c", "μ = mean state over reference cells whose read token matches this cell's.", 20),
    "kmx64": Centre("Cluster mean (label-free)", "#c2417a", "#d55181", "μ = mean of the cell's k-means cluster (k = 64) "
                    "over every family's fit read cells: no family label (S4).", 40),
    "knnx8": Centre("8 nearest cells", "#008300", "#2fa52f", "μ = mean of the 8 nearest fit read cells of any family "
                    "(cosine, own item excluded; S4).", 41),
    "u1rel": Centre("Same offset in the read span", "#6250d6", "#9085e9", "μ = mean over reference cells at the same "
                    "offset from the end of their read span, any token (U1; = family mean on single-cell families).", 30),
    "u1carpos": Centre("Same sentence, same position", "#e34948", "#e66767", "μ = mean over items with the same read-span "
                       "text at the same index (umot's carpos; reads the prompt in the mention control; U1).", 31),
    "s8eb3": Centre("Position → token dial (EB, k=3)", "#8a5a00", "#b07a1a", "μ = (n·μ_offset+token + 3·μ_offset) / (n + 3), "
                    "n = same-offset same-token cells: rare tokens shrink to the position mean (S8).", 32),
    "pco16": Centre("Family mean + top 16 PCs removed", "#7a4fb8", "#a07ad6", "g = μ_fam + P(h − μ_fam), P the projection "
                    "on the family's top 16 principal directions (own group excluded): its axes of variation (S7).", 15),
    "xl4": Centre("State 4 layers earlier", "#5f6b7a", "#8a96a5", "g = the cell's own state at layer l − 4: read only "
                  "what layers l−3..l wrote (S9; null against a random earlier layer).", 60),
    "s13uni": Centre("Pulled-back chat unigram prior", "#1f77b4", "#4a9bd6", "g = the least-squares pullback through the "
                     "readout map of the chat corpus's log unigram frequency: a principled fixed token bias, no bench data (S13).", 70),
    "s13nt": Centre("Pulled-back next-token prior", "#17becf", "#4fd3e0", "g = family mean (own group excluded) of the "
                    "pulled-back next-token log-softmax of the reference cells (S13).", 71),
    "s14fam64": Centre("Family mean + template directions removed", "#9467bd", "#b48ad6", "g = μ_fam + P(h − μ_fam), P the "
                       "projection on the lens's reading directions of 64 template tokens (S14).", 72),
    "s15famtop32": Centre("Family mean + J's top 32 directions removed", "#8c564b", "#a8766b", "g = μ_fam + P(h − μ_fam), P "
                          "the projection on J's 32 most amplified input directions (S15).", 73),
    # constant-mu exploration (x1-x11, notes/predictions.md; page "Constant μ exploration")
    "pos": Centre("Same position", "#8a6d5b", "#b09080", "μ = mean state at the same absolute position in a reference corpus (x1).", 33),
    "gen": Centre("Own-item synthetic refs", "#9c2f6b", "#c85a95", "μ = mean of 8 prompts the model wrote from the item itself (leaks its answer; x8).", 70),
    "genx": Centre("Synthetic refs, 1 example", "#0b7fa6", "#3fa9d0", "μ = mean of 8 prompts the model wrote from one other item (x9).", 71),
    "genfam": Centre("Synthetic family mean", "#0b7fa6", "#3fa9d0", "μ = prompts the model wrote from every other item, pooled (x9).", 76),
    **{f"genk:{k}": Centre(f"Synthetic refs, {k} examples", "#0b7fa6", "#3fa9d0",
                           f"μ = mean of prompts the model wrote from {k} other items (x10).", 71 + k.bit_length()) for k in (2, 4, 8)},
    "glos:word": Centre("Glossary word, generated", "#6d7f00", "#9aad1f", "μ = mean of 64 texts the model wrote from the family's glossary word (x11).", 80),
    "glos:desc": Centre("Glossary entry, generated", "#6d7f00", "#9aad1f", "μ = mean of 64 texts written from the glossary word plus a definition (x11).", 81),
    "glosx:desc": Centre("Wrong glossary entry", "#6d7f00", "#9aad1f", "Control: another family's glossary entry (x11).", 82),
    "glosb:word": Centre("Blind glossary word", "#8f7a00", "#bfa62a", "μ = 64 texts from the entry the model wrote from the bench README (x13).", 83),
    "glosb:desc": Centre("Blind glossary entry", "#8f7a00", "#bfa62a", "As the blind word, with the model's definition (x13).", 84),
    "glosall:word": Centre("Universal glossary (word)", "#4d5a00", "#7d8c1a", "One μ for every family: all 7 glossary-word sets (x14).", 85),
    "glosall:desc": Centre("Universal glossary (entry)", "#4d5a00", "#7d8c1a", "One μ for every family: all 7 glossary-entry sets (x14).", 86),
    "glos:none": Centre("No glossary entry", "#6d7f00", "#9aad1f", "Control: 64 varied short texts from no entry (x14).", 87),
    "gentok": Centre("Synthetic refs, same token", "#0b7fa6", "#3fa9d0", "μ = other items' written prompts at the same read token (x17).", 77),
    "null": Centre("Minimal prompts", "#008300", "#2fa52f", "μ = 16 minimal inputs in the family's format (x14).", 96),
    "uncond": Centre("Unconditional text", "#008300", "#2fa52f", "μ = 64 texts the model sampled from an empty context (x14).", 97),
    "fitmu": Centre("The lens's own data", "#8a6d5b", "#b09080", "μ = mean over the J-lens's own fitting cells (x20).", 34),
    **{f"pcw:{k}": Centre(f"Wikitext top {k} PCs removed", "#8a6d5b", "#b09080",
                          f"g = m + (I − P_{k})(h − m), wikitext mean m and top {k} PCs (x14).", 35 + k // 16) for k in (4, 16)},
    "massive:4": Centre("Massive dims to mean", "#8a6d5b", "#b09080", "The 4 largest wikitext-mean dimensions held at their mean (x14).", 37),
    "massivez:4": Centre("Massive dims zeroed", "#8a6d5b", "#b09080", "The 4 largest wikitext-mean dimensions set to 0 (x14).", 38),
    # x24: what makes model-written text work (source, length, style, read position)
    "glos:wshort": Centre("Short wikitext sentences", "#8a6d5b", "#b09080", "μ = 64 wikitext sentences of 10-18 tokens, at the final token (x24).", 39),
    "glos:wcut": Centre("Short wikitext, last word cut", "#8a6d5b", "#b09080", "As short wikitext, read at the token before the last word (x24).", 39),
    "glos:mwiki": Centre("Model-written, encyclopedic", "#6d7f00", "#9aad1f", "μ = 64 short sentences the model wrote in an encyclopedia's style (x24).", 88),
    "glos:mcut": Centre("No entry, last word cut", "#6d7f00", "#9aad1f", "The no-entry texts read at the token before their last word (x24).", 89),
    # x23: which representation of the context
    **{f"sent:{a}": Centre(f"Own prefix mean × {a}", "#a03c9e", "#c46cc2", f"μ = {a} × mean of the input's own earlier states (x23 A).", 100 + k)
       for k, a in enumerate(("0.25", "0.5", "1"))},
    "sentx:1": Centre("Own prefix mean, read cell out", "#a03c9e", "#c46cc2", "μ = mean of the input's states before the read cell (x23 A).", 103),
    "sentnn:8:all": Centre("8 nearest prefixes", "#a03c9e", "#c46cc2", "μ = mean read state of the 8 fit inputs whose prefix means are nearest, any family (x23 B).", 104),
    "sentnn:8:others": Centre("8 nearest prefixes, other families", "#a03c9e", "#c46cc2", "As 8 nearest prefixes, the read family excluded (x23 B).", 105),
    "word:ctx": Centre("Situation word per input", "#a03c9e", "#c46cc2", "μ = 32 texts written from the word the model named for this input's situation (x23 C).", 106),
    "word:topic": Centre("Topic word per input", "#a03c9e", "#c46cc2", "Control: 32 texts from the word for what the input is about (x23 C).", 107),
    **{f"word:ctx{k}": Centre(f"Situation word, {lab}", "#a03c9e", "#c46cc2", f"As the situation word, named with {lab} (x23b).", 107 + k)
       for k, lab in ((2, "rules"), (3, "worked examples"), (4, "rules + examples"))},
    **{f"dict:{m}:0.5": Centre(lab, "#667185", "#8f9aab", d, 90 + k) for k, (m, lab, d) in enumerate([
        ("fam", "Family word", "μ = 0.5 × typical norm × the family's glossary word direction (x2/x3)."),
        ("strat", "Stratum word", "μ from the item's stratum word in bank metadata, e.g. 'country' (x2/x3)."),
        ("llm", "Judged word", "μ from the word the 27B judged fittest for the item (x2/x3)."),
        ("derang", "Wrong word", "Control: an unrelated family's word (x2/x3)."),
    ])},
    "dict:fam2+:0.25": Centre("Bank + test name", "#a06a3b", "#c99064", "All-family bank plus 0.25 × the test-name direction (x5).", 95),
    # night-2 finalists (studies/e1-catalog-lines.md, instance B)
    "s14t64": Centre("Template reading directions removed", "#d62728", "#e05a5a", "Label-free, no reference cells: g = P h, P "
                     "the projection on the lens's reading directions of 64 template tokens (S14).", 74),
    "sched:40:kmx64+s14t64": Centre("S14k: clusters ≤ L40, template above", "#ff7f0e", "#ffa04d", "Label-free: the cell's "
                                    "k-means cluster mean (kmx64) up to L40, the template projection above (S14k; did not "
                                    "replicate on fresh val2).", 75),
    "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5": Centre("S14b: clusters ≤ L40, template − ½ cluster above",
        "#bcbd22", "#d4d55a", "Label-free: kmx64 up to L40; above, the template projection of h − 0.5·μ_cluster (S14b).", 76),
    "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5": Centre("S14b-x: template − ½ 8-nearest above", "#2ca02c",
        "#5cc25c", "Label-free: kmx64 up to L40; above, the template projection of h − 0.5·(mean of the 8 nearest fit "
        "cells sharing no carrier with the cell) (A, S14; fresh val2+val3 +0.039).", 77),
    "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5": Centre("S14bL: as S14b-x, other languages only", "#00a6a6",
        "#33c4c4", "Label-free finalist: as S14b-x, the late neighbours also exclude cells whose prompt is in the cell's "
        "own non-English language (detected from the prompt text): keeps multilingual_mt's language unit (A, S14).", 78),
    "knnxs8": Centre("8 nearest cells, other carriers only", "#4c9a2a", "#73b852", "Label-free: the mean of the 8 nearest "
                     "fit read cells of any family, none sharing the cell's carrier sentence (S16c: knnx8's same-sentence "
                     "leak removed).", 79),
    "s20xt:1": Centre("S20x: fam + learned correction (supervised)", "#e377c2", "#f0a0d8", "SUPERVISED (other families' "
                      "fit targets): the family mean plus the average of the other families' target-fitted constant "
                      "corrections (S20), the read family and its _mt twin left out (S20x; fresh val2+val3 +0.051).", 80),
    "s20xon:1:kmx64": Centre("Clusters + learned correction (supervised)", "#a05195", "#c07ab5", "SUPERVISED: the k-means "
                             "cluster mean (kmx64) plus S20x's correction at every layer (S20x / S23b; fails the "
                             "multilingual_mt guardrail on val, cos).", 81),
    "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5": Centre("S21b: S14b + early learned correction "
        "(supervised)", "#7f7f7f", "#a5a5a5", "SUPERVISED: S14b with S20x's correction added up to L40 (S21; fresh "
        "val2+val3 +0.039).", 82),
    "s20xonrms:1:kmx64": Centre("Clusters + learned correction, rms-fitted (supervised)", "#c49c94", "#d8b8b0",
        "SUPERVISED: as s20xon:1:kmx64 with the corrections refitted through the rms map (read with |rms).", 83),
    "s18c8": Centre("Family mean without its 8 outlier coordinates", "#6b4226", "#8f6a4f", "g = μ_fam with its 8 largest "
                    "coordinates zeroed: reads like fam (S18: the outliers hold most of the norm and none of the gain).", 84),
}
#: Colours for centres without an entry (picked by a hash of the name, so a centre keeps its colour).
SPARE = [("#6250d6", "#9085e9"), ("#c2417a", "#d55181"), ("#008300", "#2fa52f"), ("#e34948", "#e66767")]

REFS = {
    "": "",
    "self": "leave-one-out on the read bank",
    "fit": "fitted on the dev fit split (held out)",
    "corpus": "wikitext-103 validation passages, every position",
    "corpus8": "wikitext-103 validation passages, positions 8 on",
    "sents": "final tokens of standalone wikitext sentences",
    "fitall": "every dev family's fit prompts",
    "fitothers": "every OTHER dev family's fit prompts",
    "plainothers": "every OTHER plain-render family's fit prompts",
}
REF_SHORT = {"": "", "self": "LOO", "fit": "fit", "corpus": "corpus", "corpus8": "corpus", "sents": "sentences",
             "fitall": "all-family bank", "fitothers": "other families", "plainothers": "plain bank"}
#: Words worth watching in a family's readouts besides its targets (Passage → readouts, "Tracked tokens"), grouped by
#: idea: a group is offered once, as whichever form places best at the read cell. All single tokens with a leading
#: space in Qwen3.6. directed_modulation: words about holding, attending to or pushing away a thought.
WATCH = {
    "directed_modulation": {
        "think": ["think", "thinking", "thought", "thoughts"],
        "focus": ["focus", "focusing", "concentrate", "concentrating", "attention", "attend"],
        "mind": ["mind", "minds", "mental", "mentally"],
        "imagine": ["imagine", "imagining", "picture", "visualize", "dream"],
        "remember": ["remember", "recall", "memory"],
        "hold": ["keep", "hold", "holding"],
        "avoid": ["avoid", "avoiding", "resist"],
        "ignore": ["ignore", "ignoring", "forget", "forgetting"],
        "suppress": ["suppress", "suppressing", "distract", "distraction"],
        "aware": ["aware", "awareness", "conscious", "consciously", "notice"],
        "subconscious": ["subconscious", "unconscious"],
        "hidden": ["secret", "secretly", "hidden", "hide", "silent", "silently"],
        "inner": ["inner", "internal", "background"],
        "urge": ["want", "desire", "urge", "tempted", "obsess"],
    },
}

READOUTS = {"cos": "the bench's cosine readout", "rms": "jle's RMS-norm readout"}
LENSES = {"jlens": "J-lens n1000 (a4114d7)", "jpp": "J++ lens (6c96867)", "logit": "logit lens (no map)"}
LENSES["ols"] = "regression-slope map (x21: h_63 on h_l over the J-lens's own fitting cells)"  # out/maps/ols.pt


#: Control prefixes on a centre (jlm.centres.CONTROLS): label, short tag, what the control does.
CONTROLS = {
    "shuf": ("Shuffled g", "shuf", "Control: each cell is read with the g of another read cell at the same layer "
             "(a seeded random cycle), so a gain that survives it does not come from matching g to the cell."),
    "rand": ("Random g", "rand", "Control: g replaced by a random direction (one per layer) with each cell's ‖g‖, so a "
             "gain that survives it is a norm or bias effect, not content."),
}


def _mix(hexc: str, toward: str, t: float) -> str:
    """``hexc`` moved a share ``t`` of the way to ``toward`` (both #rrggbb)."""
    a = [int(hexc[k : k + 2], 16) for k in (1, 3, 5)]
    b = [int(toward[k : k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b, strict=True))


# jlm.mu module -> the study that owns its centres (notes/iteration-anthony/studies/<id>.md)
STUDY_OF_MODULE = {"clusters": "S4", "u1": "U1", "s5": "S5", "s8": "S8", "infra_smoke": "infra"}


@lru_cache(maxsize=1024)
def study(centre: str) -> str:
    """The study a centre comes from: "baseline" for zero / fam / tok, else its jlm.mu module (S7, U1, ...)."""
    try:
        from jlm import centres

        if centre not in centres.CENTRES:
            import jlm.mu  # noqa: F401
        cls = centres.CENTRES[centre]
    except Exception:
        return "other"
    mod = getattr(cls, "func", cls).__module__
    if mod == "jlm.centres":
        return "baseline"
    short = mod.rpartition(".")[2]
    return STUDY_OF_MODULE.get(short, short)


@lru_cache(maxsize=256)
def _doc(centre: str) -> str:
    """The centre class's own one-line ``doc`` (jlm.centres / jlm.mu), or "" when it cannot be built here."""
    try:
        from jlm import centres

        return str(getattr(centres.make(centre), "doc", "") or "")
    except Exception:
        return ""


#: Who added a centre, for the pickers' groups: a jlm.mu module says so with a line ``OWNER = "<name>"``; this covers
#: modules without one (by module name). Centres in jlm.centres are the shared baselines.
MODULE_OWNERS = {"constant_mu": "Maya"}
BASELINES, CONTROLS_GROUP, OTHERS = "Baselines", "Controls", "Other centres"


@lru_cache(maxsize=1024)
def _module(centre: str):
    """The module that registers ``centre`` (None when it cannot be built here)."""
    try:
        import importlib

        import jlm.mu  # noqa: F401  (registers every study module's centres)
        from jlm import centres

        f = centres.CENTRES.get(centre) or centres.PARAMETRIC.get(centre.partition(":")[0])
        return importlib.import_module(getattr(f, "func", f).__module__)
    except Exception:
        return None


@lru_cache(maxsize=1024)
def owner(centre: str) -> str:
    """The name of whoever added ``centre`` ("" for a shared baseline, "?" when its module names nobody)."""
    mod = _module(centre)
    if mod is None:
        return "?"
    if mod.__name__ == "jlm.centres":
        return ""
    return getattr(mod, "OWNER", None) or MODULE_OWNERS.get(mod.__name__.rpartition(".")[2], "?")


#: A person's best centres so far: a jlm.mu module lists its own with ``CANDIDATES = ("<centre>", ...)``. Once anyone
#: names a candidate, the pickers split that person's centres into "<name>'s best candidates" and "<name>'s experimental centres".
@lru_cache(maxsize=1)
def _candidates() -> dict[str, frozenset[str]]:
    import sys

    import jlm.mu  # noqa: F401

    out: dict[str, set[str]] = {}
    for name, mod in list(sys.modules.items()):
        if name.startswith("jlm.mu") and getattr(mod, "CANDIDATES", None):
            o = getattr(mod, "OWNER", None) or MODULE_OWNERS.get(name.rpartition(".")[2], "?")
            out.setdefault(o, set()).update(mod.CANDIDATES)
    return {o: frozenset(c) for o, c in out.items()}


def candidate(centre: str) -> bool:
    """Whether ``centre`` is one of its owner's declared best candidates."""
    return centre in _candidates().get(owner(centre), ())


def group(a: "Arm") -> str:
    """The picker group an arm is listed under: its (inner) centre's owner, split into candidates and experimental when
    the owner has declared candidates. J++ arms go with their centre; every shuf. / rand. arm is under "Controls"."""
    if a.control:
        return CONTROLS_GROUP
    c = a.inner
    o = owner(c)
    if o in ("", "?"):
        return BASELINES if o == "" else OTHERS
    if o not in _candidates():
        return f"{o}'s centres"
    return f"{o}'s best candidates" if candidate(c) else f"{o}'s experimental centres"


def group_order(g: str) -> tuple:
    """Baselines first, then each person's centres by name (candidates before experimental), then the controls, then
    the rest."""
    return (g != BASELINES, g == OTHERS, g == CONTROLS_GROUP, g.rpartition("'s ")[0], g.endswith("experimental centres"), g)


def folded(g: str) -> bool:
    """Picker groups drawn collapsed: a person's experimental centres and the controls."""
    return g.endswith("experimental centres") or g == CONTROLS_GROUP


def beside(g: str) -> str | None:
    """The picker group drawn to the right of ``g``: the controls beside the (first) best candidates."""
    return CONTROLS_GROUP if g.endswith("best candidates") else None


@dataclass(frozen=True)
class Map:
    short: str  # label suffix on its arms
    light: str  # colour of its uncentred arm; its centred arms take a spare colour
    dark: str


MAPS = {"jpp": Map("J++", "#c2417a", "#d55181")}


@dataclass(frozen=True)
class Arm:
    name: str  # e.g. "fam@fit|cos"
    centre: str
    ref: str
    readout: str
    lens: str = "jlens"

    @property
    def control(self) -> str:
        """``shuf`` / ``rand`` for a control arm, else ""."""
        head, dot, _ = self.centre.partition(".")
        return head if dot and head in CONTROLS else ""

    @property
    def inner(self) -> str:
        """The centre a control wraps (the centre itself for a non-control arm)."""
        return self.centre.partition(".")[2] if self.control else self.centre

    @property
    def info(self) -> Centre | None:
        return CENTRES.get(self.inner)

    @property
    def dash(self) -> str:
        """Plotly line dash: dashed for controls, dotted for leave-one-out references, solid otherwise."""
        return "dash" if self.control else "dot" if self.ref == "self" else "solid"

    @property
    def map(self) -> Map | None:
        return MAPS.get(self.lens)

    @property
    def label(self) -> str:
        base = self.info.label if self.info else self.inner
        if self.control:
            base = f"{CONTROLS[self.control][0]} · {base}"
        if self.map:
            base = f"{self.map.short} · {base}" if self.centre != "zero" else f"Plain {self.map.short}"
        return base + (f" · {REF_SHORT.get(self.ref, self.ref)}" if self.ref else "")

    @property
    def colour(self) -> str:
        if self.control:  # the inner arm's colour, faded toward the page background
            base = parse(self.name.replace(self.centre, self.inner, 1)).colour
            return _mix(base, ui.c("bg"), 0.45)
        if self.map and self.centre == "zero":
            return self.map.dark if ui.night() else self.map.light
        if self.info and not self.map:
            return self.info.dark if ui.night() else self.info.light
        light, dark = SPARE[int(hashlib.md5(f"{self.lens}:{self.centre}".encode()).hexdigest(), 16) % len(SPARE)]
        return dark if ui.night() else light

    @property
    def blurb(self) -> str:
        what = self.info.blurb if self.info else (
            (_doc(self.inner).rstrip(".") + ".") if _doc(self.inner) else "Not described yet: add it to CENTRES in dashboard/catalog.py.")
        if self.control:
            what = CONTROLS[self.control][2] + " Inner centre: " + what
        if self.map:
            what = f"Read through the {LENSES[self.lens]} instead of the J-lens. " + what
        return what + (f" Reference: {REFS.get(self.ref, self.ref)}." if self.ref else "")

    @property
    def sort_key(self) -> tuple:
        return (self.lens != "jlens", self.info.order if self.info else 99, self.inner, list(CONTROLS).index(self.control) + 1
                if self.control else 0, ["", "fit", "self"].index(self.ref) if self.ref in ("", "fit", "self") else 9)


#: Centre heads selected only on request: the constant-mu exploration's many variants (x1-x12; shown together on
#: the "Constant μ exploration" page), which would otherwise crowd every page that opens with held-out centres.
OPT_IN = {"pos", "cpt", "cptc", "cpt+", "cptc+", "dict", "gen", "genx", "genfam", "genk", "glos", "glosx", "glosb",
          "glosall", "gentok", "null", "uncond", "fitmu", "pcw", "massive", "massivez"}


# Selected when a page opens (every other arm is one click away): the plain J-lens, the family mean, the plain J++
# lens and Anthony's best candidates (S4's knnx8, S7's pco16). An entry may carry a lens prefix ("jpp:zero").
# Rendering every evaluated centre by default made the Explore pages slow.
DEFAULT_CENTRES = ("zero", "fam", "jpp:zero", "knnx8", "pco16")


def default_on(a: Arm, held_ref: str) -> bool:
    """Selected when a page opens: the plain J-lens and the ``DEFAULT_CENTRES`` fitted on ``held_ref``. Controls and
    other maps (J++) are opt-in."""
    return a.lens == "jlens" and not a.control and (a.centre == "zero" or (
        a.centre in DEFAULT_CENTRES and a.ref == held_ref and a.centre.split(":")[0] not in OPT_IN))


def defaults(arms: list[Arm], held_ref: str) -> list[str]:
    """Names of the arms a page opens with: per ``DEFAULT_CENTRES`` entry, its arm on ``held_ref`` when there is one,
    else its arm on the other reference (on fit, the studies fitted most centres ``@fit``, own group left out, not
    leave-one-out ``@self``)."""
    out = []
    for entry in DEFAULT_CENTRES:
        want = parse(entry)
        mine = [a for a in arms if a.lens == want.lens and not a.control and a.centre == want.centre]
        pick = next((a for a in mine if a.centre == "zero" or a.ref == held_ref), next(iter(mine), None))
        if pick:
            out.append(pick.name)
    return out or [arms[0].name] if arms else []


def parse(name: str) -> Arm:
    lens, colon, rest = name.partition(":")  # a lens prefix only when it names a lens: centres hold ':' too
    if not (colon and lens in LENSES):
        lens, rest = "jlens", name
    head, _, readout = rest.partition("|")
    centre, _, ref = head.partition("@")
    return Arm(name, centre, ref, readout, lens)


def from_dir(dirname: str) -> str:
    """``fam-at-fit__cos`` -> ``fam@fit|cos``, ``jpp~zero__cos`` -> ``jpp:zero|cos`` (the inverse of sources.arm_dir)."""
    return dirname.replace("-at-", "@").replace("__", "|").replace("~", ":")
