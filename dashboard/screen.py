"""Data for the constant-mu exploration page: our own centres (x1-x12, notes/predictions.md) under the agreed
protocol (strict, 7 families, fit and val, rms), read from the pipeline's store out/eval/<family>/<split>/<arm>/
like every other page, and scored with the pipeline's own strict rule (jlm.score) and paired item bootstrap.
Also: what each centre is made of (glossary entries, the texts the model wrote, the word dictionary), per-item
top-10 readouts, and the other techniques the store holds (other lenses, other studies' centres) for comparison.
"""

import json
from collections import defaultdict
from pathlib import Path

import streamlit as st

import catalog
import hfsync
import sources
import ui
from jlm import REPO_ROOT, hfdata

SCREEN = sources.EVAL  # one store for every page (was out/screen before the iteration merge)
PROXY = ["typo", "association", "basic_readout", "multihop", "multilingual"]
CHAT = ["user_modeling", "directed_modulation"]
FAMILIES = PROXY + CHAT
PLAIN = "zero|rms"

#: Tier of a centre: (key, label, light colour, dark colour, what it needs at read time). Order = ladder order.
TIERS = [
    ("plain", "Plain J-lens", "#3b63c9", "#6b8de6", "nothing"),
    ("family", "Family data (the target)", "#0f8a77", "#22a085", "a bank of the family's own prompts"),
    ("synthetic", "Model-written from examples", "#6250d6", "#9085e9", "a few example prompts; the model writes the rest"),
    ("glossary", "Model-written from a glossary entry", "#c2417a", "#d55181", "one glossary entry; the model writes the rest"),
    ("bank", "Other tasks' prompts", "#b9781a", "#c98a2c", "a frozen bank of other tasks' prompts"),
    ("word", "One word as μ", "#667185", "#8f9aab", "one dictionary word per family, stratum or item"),
    ("free", "Model-only references", "#008300", "#2fa52f", "the prompt format; the model writes the rest, or nothing"),
    ("corpus", "Generic text", "#8a6d5b", "#b09080", "wikitext"),
]
TIER = {t[0]: t for t in TIERS}


def C(tier, label, blurb, constant, ref, exp):
    return {"tier": tier, "label": label, "blurb": blurb, "constant": constant, "ref": ref, "exp": exp}


#: arm (without readout) -> what it is. ``constant``: how μ varies (the goal is one vector per layer that needs no
#: task data); ``ref``: what it is fitted on and what is held out.
CENTRES = {
    "zero": C("plain", "plain (μ = 0)", "The released lens: no centre.", "–", "nothing", "reference"),
    "fam@fit": C("family", "family mean", "Mean state over the family's dev fit prompts at the read cell.",
                 "one per layer and family", "the family's fit split (on fit itself: own item left out)", "reference"),
    "tok@fit": C("family", "same-token mean", "Mean over fit cells reading the same token (< 3 cells: the family mean).",
                 "one per layer and read token", "the family's fit split, same token, own item left out", "reference"),
    "gen@self": C("synthetic", "own-item refs", "The model writes 8 prompts of the same kind from the item itself.",
                  "one per item (leaks its answer)", "8 texts written from the item being read", "x8"),
    "genx@self": C("synthetic", "1 example", "8 prompts the model wrote from ONE other item of the family.",
                   "one per item", "the next item's 8 written texts (sorted ids), never its own", "x9"),
    "genk:2@self": C("synthetic", "2 examples", "8 written prompts each from 2 other items.", "one per item",
                     "the next 2 items' written texts", "x10"),
    "genk:4@self": C("synthetic", "4 examples", "8 written prompts each from 4 other items.", "one per item",
                     "the next 4 items' written texts", "x10"),
    "genk:8@self": C("synthetic", "8 examples", "8 written prompts each from 8 other items.", "one per item",
                     "the next 8 items' written texts", "x10"),
    "genfam@self": C("synthetic", "all examples", "Written prompts of every other item, pooled.",
                     "≈ one per layer (own item's texts left out)", "every other item's written texts", "x9"),
    "gentok@self": C("synthetic", "token-matched examples", "Other items' written prompts read at the same token "
                     "(< 3 such cells: all examples).", "one per layer and read token",
                     "every other item's written texts, same read token", "x17"),
    "glos:word@self": C("glossary", "glossary word", "64 texts the model wrote from the family's glossary word alone.",
                        "one per layer and family", "64 texts from the word; no bank item seen", "x11, x12"),
    "glos:desc@self": C("glossary", "glossary entry", "64 texts written from the glossary word plus a one-line definition.",
                        "one per layer and family", "64 texts from the entry; no bank item seen", "x11, x12"),
    "glosx:desc@self": C("glossary", "wrong entry", "Control: another family's glossary entry.",
                         "one per layer and family", "64 texts from another family's entry", "x11, x12"),
    "glosb:word@self": C("glossary", "blind glossary word", "The 27B wrote the entry itself from one sentence of the "
                         "bench's README; 64 texts from its word.", "one per layer and family",
                         "64 texts from the model's own entry; no bank item or result seen", "x13"),
    "glosb:desc@self": C("glossary", "blind glossary entry", "As above, from the model's word plus its definition.",
                         "one per layer and family", "64 texts from the model's own entry", "x13"),
    "glosall:word@self": C("glossary", "universal glossary (word)", "ONE μ for every family: the mean of all 7 families' "
                           "glossary-word sets, equal weight.", "one per layer", "all 7 glossary-word sets", "x14"),
    "glosall:desc@self": C("glossary", "universal glossary (entry)", "As above, over the 7 glossary-entry sets.",
                           "one per layer", "all 7 glossary-entry sets", "x14"),
    "glos:none@self": C("glossary", "no entry", "Control: 64 varied short texts written from no entry at all (chat: "
                        "the format line only).", "one per layer and family (format only)", "64 model-written texts", "x14"),
    "fam@plainothers": C("bank", "plain-prompt bank", "Mean over OTHER plain-render families' fit prompts.",
                         "one per layer", "fit splits of the other plain-text families", "x6"),
    "fam@fitall": C("bank", "all-family bank", "Mean over every dev family's fit prompts.", "one per layer",
                    "fit splits of all 7 families", "x4"),
    "fam@fitothers": C("bank", "other-family bank", "Mean over every OTHER dev family's fit prompts.", "one per layer",
                       "fit splits of the 6 other families", "x4"),
    "dict:fam2+:0.25@fitall": C("bank", "bank + test name", "All-family bank plus 0.25 × the test-name word's direction.",
                                "one per layer and family", "all-family bank; the test's name (dictionary)", "x5"),
    "dict:fam:0.5@fit": C("word", "family word", "0.5 × typical ‖h‖ × the family word's direction.",
                          "one per layer and family", "the word's carrier phrases; ‖h‖ from fit", "x2, x3"),
    "dict:strat:0.5@fit": C("word", "stratum word", "The item's stratum word from bank metadata (e.g. 'country').",
                            "one per layer and stratum", "the word's carrier phrases", "x2, x3, x7"),
    "dict:llm:0.5@fit": C("word", "judged word", "The dictionary word the 27B judged fittest for the item's text.",
                          "one per item", "the word's carrier phrases; the 27B's label", "x2, x3"),
    "dict:derang:0.5@fit": C("word", "wrong word", "Control: an unrelated family's word.", "one per layer and family",
                             "the word's carrier phrases", "x2, x3, x7"),
    "fam@corpus8": C("corpus", "corpus mean", "Mean over wikitext positions 8 and on.", "one per layer",
                     "wikitext-103 validation paragraphs", "x1, x4"),
    "tok@corpus8": C("corpus", "corpus same-token", "Wikitext mean over positions reading the same token.",
                     "one per layer and token", "wikitext-103 validation paragraphs", "x1, x4"),
    "pos@corpus": C("corpus", "corpus same-position", "Wikitext mean at the same absolute position.",
                    "one per layer and position", "wikitext-103 validation paragraphs", "x1"),
    "fam@sents": C("corpus", "sentence-end mean", "Mean at the final token of standalone wikitext sentences.",
                   "one per layer", "standalone wikitext sentences", "x1, x4"),
    "fitmu@self": C("corpus", "the lens's own data", "Mean state over the cells the J-lens was fitted on (wikitext "
                    "train, its 1000 prompts, positions 16 to 126).", "one per layer", "the J-lens's fitting prompts", "x20"),
    "pcw:4@self": C("corpus", "wikitext PCs removed (4)", "Remove the wikitext mean and its top 4 principal directions.",
                    "one operation per layer", "8,192 wikitext-103 cells", "x14"),
    "pcw:16@self": C("corpus", "wikitext PCs removed (16)", "As above, top 16 principal directions.",
                     "one operation per layer", "8,192 wikitext-103 cells", "x14"),
    "massive:4@self": C("corpus", "massive dims to mean", "The 4 largest wikitext-mean dimensions held at their mean.",
                        "one operation per layer", "8,192 wikitext-103 cells", "x14"),
    "massivez:4@self": C("corpus", "massive dims zeroed", "The 4 largest wikitext-mean dimensions set to 0.",
                         "one operation per layer", "8,192 wikitext-103 cells", "x14"),
    "null@self": C("free", "minimal prompts", "16 minimal inputs read like the family's items (one word; a neutral "
                   "message or sentence in the chat template).", "one per layer and family (format only)",
                   "16 fixed minimal prompts", "x14"),
    "uncond@self": C("free", "unconditional text", "64 texts the model sampled from an empty context, read like the "
                     "family's items.", "one per layer and family (format only)", "64 unconditional samples", "x14"),
}

#: The other readers the store can hold (arm prefixes), for the comparison section.
LENS_NAMES = {"jlens": "J-lens (n1000)", "jpp": "J++ lens", "logit": "logit lens",
              "ols": "regression slope (x21)"}

#: What each WorkspaceBench family asks, where it is read, and what strict counts as a hit.
FAMILY_DOC = {
    "typo": ("A sentence whose last word is misspelled.", "the final token (the misspelled word)",
             "the intended word (e.g. 'difer' → differ)"),
    "association": ("A scene that evokes one concept, place, event or activity without naming it.", "the final token",
                    "the evoked concept (e.g. a climbing scene → climbing)"),
    "basic_readout": ("A prompt that stops right before an obvious one-word answer: a fact, a number or a name.",
                      "the final token", "the answer (e.g. 'Brussels is the capital of' → Belgium)"),
    "multihop": ("A 'Fact:' sentence that refers to something only indirectly and stops before an answer that needs "
                 "it first.", "the final token", "the bridge entity, never named (e.g. Bosphorus city → Turkey, "
                 "not the answer Ankara)"),
    "multilingual": ("A prompt in another language that stops before a one-word answer.", "the final token",
                     "the answer's English meaning (e.g. 'Le contraire de riche est' → poor)"),
    "user_modeling": ("A user's message lets slip something about who they are (gender, age, job, country, …), "
                      "followed by a request.", "from the request sentence's start through the chat template",
                      "the implied attribute (e.g. 'my wife and I' → male)"),
    "directed_modulation": ("The model is told to think (or not) about a concept while copying a given sentence.",
                            "every token of the copied sentence (teacher-forced reply)",
                            "the held concept (e.g. spatula); scored by the judge, content-bound"),
}


def info(arm: str) -> tuple:
    """(tier tuple, label, sentence) for an arm name with or without its readout."""
    base = arm.split("|")[0]
    c = CENTRES.get(base) or {"tier": "corpus", "label": base,
                              "blurb": "Not described yet: add it to CENTRES in dashboard/screen.py."}
    return TIER[c["tier"]], c["label"], c["blurb"]


def colour(arm: str) -> str:
    t = info(arm)[0]
    return t[3] if ui.night() else t[2]


def stamp() -> float:
    files = [*SCREEN.glob("*/*/summary.json"), *SCREEN.glob("*/*/*/readouts.jsonl")]
    return max((p.stat().st_mtime for p in files), default=0.0)


def all_arms(family: str, split: str) -> list[str]:
    """Every arm with readouts for this bank (any lens, any study)."""
    d = SCREEN / family / split
    return sorted(catalog.from_dir(p.parent.name) for p in d.glob("*/readouts.jsonl")) if d.exists() else []


def arms(family: str, split: str, readout: str) -> list[str]:
    """This page's arms (J-lens, rms or cos) with readouts for this bank."""
    return [n for n in all_arms(family, split) if n.endswith("|" + readout) and n.split("|")[0] in CENTRES]


def readouts(split: str) -> list[str]:
    """Readouts with this page's arms on this split (rms first: the house readout)."""
    found = {p.parent.name.rsplit("__", 1)[-1] for p in SCREEN.glob(f"*/{split}/*/readouts.jsonl")
             if catalog.from_dir(p.parent.name).split("|")[0] in CENTRES}
    return [r for r in ("rms", "cos") if r in found]


@st.cache_data(show_spinner="Scoring…", max_entries=64)
def passes_of(family: str, split: str, names: tuple[str, ...], _stamp: float) -> tuple[list[str], dict[str, dict[str, bool]]]:
    """(scored item ids, arm -> item -> strict pass) for the named arms present on this bank."""
    from jlm import banks as jbanks
    from jlm import score as jscore

    summ = SCREEN / family / split / "summary.json"
    if not summ.exists():
        return [], {}
    r = json.loads(summ.read_text())["result"]
    if "scored_ids" not in r:
        return [], {}
    bank = jbanks.load(family, split)
    out = {}
    for a in names:
        p = SCREEN / family / split / sources.arm_dir(a) / "readouts.jsonl"
        if p.exists():
            out[a] = jscore.strict_items(sources._jsonl(p), bank)
    return r["scored_ids"], out


def passes(family: str, split: str, readout: str, _stamp: float):
    return passes_of(family, split, tuple(arms(family, split, readout)), _stamp)


@st.cache_data(show_spinner=False, max_entries=128)
def table(family: str, split: str, names: tuple[str, ...], _stamp: float, base: str = PLAIN) -> dict[str, dict]:
    """arm -> {rate, diff, ci, n}: strict pass rate on this bank and its paired difference from ``base``."""
    from jlm import score as jscore

    ids, P = passes_of(family, split, tuple(dict.fromkeys((base, *names))), _stamp)
    if base not in P or not ids:
        return {}
    out = {}
    for a in names:
        if a in P:
            r = jscore.paired(P[a], P[base], ids)
            out[a] = {"rate": sum(P[a][i] for i in ids) / len(ids), "diff": r["diff"], "ci": r["ci95"], "n": len(ids)}
    return out


def per_family(family: str, split: str, readout: str, _stamp: float) -> dict[str, dict]:
    """This page's arms on one bank, paired against the plain lens with the same readout."""
    return table(family, split, tuple(arms(family, split, readout)), _stamp, base=f"zero|{readout}")


@st.cache_data(show_spinner=False, max_entries=64)
def pooled(families: tuple[str, ...], split: str, readout: str, _stamp: float) -> dict[str, dict]:
    """arm -> {rate, diff, ci, n, families}: pooled over the families where the arm exists, each item once."""
    from jlm import score as jscore

    per = {f: passes(f, split, readout, _stamp) for f in families}
    plain = f"zero|{readout}"
    by_arm = defaultdict(list)
    for f, (_ids, P) in per.items():
        for a in P:
            if plain in P:
                by_arm[a].append(f)
    out = {}
    for a, fams in by_arm.items():
        keys = [(f, i) for f in fams for i in per[f][0]]
        pa = {(f, i): per[f][1][a][i] for f, i in keys}
        pz = {(f, i): per[f][1][plain][i] for f, i in keys}
        r = jscore.paired(pa, pz, keys)
        out[a] = {"rate": sum(pa.values()) / len(keys), "diff": r["diff"], "ci": r["ci95"], "n": len(keys), "families": fams}
    return out


@st.cache_data(show_spinner=False, max_entries=64)
def judged(family: str, split: str, names: tuple[str, ...], _stamp: float) -> dict[str, dict]:
    """arm -> the newest judge run's {value, ci, n, label} at layers 24/36/48/60 (or any full run)."""
    out = {}
    for a in names:
        adir = sources.arm_dir(a)
        runs = sources.judge_runs(family, split, adir)
        if runs:
            out[a] = sources.judged(family, split, adir, runs[0], sources.readouts_mtime(family, split, adir))
    return out


# ------------------------------------------------------------------ what the centres are made of


def _provenance(rel: str) -> dict | None:
    """A capture's provenance JSON (small), fetched from the shared dataset when only it has it."""
    p = hfdata.ensure(rel, out=hfsync.OUT) or (sources.CAPTURES.parent / rel)
    return json.loads(Path(p).read_text()) if Path(p).exists() else None


#: x24's reference sets (glos-<variant>-<family>) have no glossary entry: what each one is instead.
X24 = {"wshort": "wikitext sentences, 10-18 tokens (x24)", "wcut": "wikitext sentences without their last word (x24)",
       "mwiki": "model-written, in an encyclopedia's style (x24)", "mcut": "the no-entry texts without their last word (x24)"}


@st.cache_data(show_spinner=False)
def glossary(_stamp: float) -> list[dict]:
    """Every glossary reference set: {family, variant, read_as, word, definition, format, texts, n, source}."""
    names = sorted({r.removeprefix("captures/").removesuffix(".provenance.json")
                    for r in hfdata.listing("captures", out=hfsync.OUT)
                    if r.startswith("captures/glos-") and r.endswith(".provenance.json")})
    out = []
    for n in names:
        d = _provenance(f"captures/{n}.provenance.json")
        if not d:
            continue
        ex = d["provenance"]["extra"]
        _, variant, rest = n.split("-", 2)
        entry, _, read_as = rest.partition("@")
        word, definition = ex.get("entry") or (X24.get(variant, ""), "")
        out.append({"set": n, "family": entry, "variant": variant, "read_as": read_as or ex.get("read_as") or entry,
                    "word": word, "definition": definition, "format": ex.get("format", ""),
                    "texts": ex.get("texts", []), "n": d["result"].get("refs"),
                    "source": "wikitext" if variant in ("wshort", "wcut") else "model"})
    return out


@st.cache_data(show_spinner=False)
def blind(_stamp: float) -> dict:
    """x13: the glossary entries the 27B wrote from each family's README sentence ({entries, descriptions})."""
    p = hfdata.ensure("captures/glossary-blind.json", out=hfsync.OUT) or (sources.CAPTURES / "glossary-blind.json")
    return json.loads(Path(p).read_text()) if Path(p).exists() else {}


@st.cache_data(show_spinner=False, max_entries=32)
def written(family: str, split: str, _stamp: float) -> dict[str, list[str]]:
    """item -> the prompts the model wrote from it (x8 generator; stored since the 2026-10-11 runs)."""
    d = _provenance(f"captures/gen-{family}-{split}.provenance.json")
    return (d or {}).get("provenance", {}).get("extra", {}).get("texts", {}) if d else {}


@st.cache_data(show_spinner=False)
def dictionary() -> dict:
    """data/abstract_concepts.json: the word dictionary of x1-x3 / x5 / x7."""
    p = REPO_ROOT / "data" / "abstract_concepts.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ------------------------------------------------------------------ items, read cell by cell


@st.cache_data(show_spinner="Loading readouts…", max_entries=64)
def tops(family: str, split: str, arm: str, layer: int | None, _mtime: float) -> dict[str, dict]:
    """item -> {pos, token, tokens, rank} at ``layer`` (None: the layer where the target ranks best). For several
    read cells (the chat families) the cell where the target ranks best is shown."""
    adir = sources.arm_dir(arm)
    cells = sources.cells(family, split, adir, _mtime)
    ranks = sources.ranks(family, split, adir, _mtime)
    best: dict[str, tuple] = {}
    for (i, L, p), r in cells.items():
        if layer is not None and L != layer:
            continue
        rk = ranks.get((i, L, p))
        key = (rk if rk is not None and rk >= 0 else 10**9, L, p)
        if i not in best or key < best[i][0]:
            best[i] = (key, L, p, r)
    return {i: {"layer": L, "pos": p, "token": r["token"], "tokens": r["tokens"], "rank": k[0] if k[0] < 10**9 else None}
            for i, (k, L, p, r) in best.items()}


def reader_arms(family: str, split: str) -> list[str]:
    """This page's centres read through any reader in the store (J-lens, J++, the logit lens), rms, J-lens first."""
    out = []
    for n in all_arms(family, split):
        a = catalog.parse(n)
        base = n.split(":", 1)[1] if a.lens != "jlens" else n
        if a.readout == "rms" and a.lens in LENS_NAMES and base.split("|")[0] in CENTRES:
            out.append(n)
    keys = list(CENTRES)
    return sorted(out, key=lambda n: (list(LENS_NAMES).index(catalog.parse(n).lens),
                                      keys.index((n.split(":", 1)[1] if catalog.parse(n).lens != "jlens" else n).split("|")[0])))


def label(arm: str) -> str:
    """'J++ · family mean': the reader, then the centre."""
    a = catalog.parse(arm)
    base = arm.split(":", 1)[1] if a.lens != "jlens" else arm
    return f"{LENS_NAMES.get(a.lens, a.lens).split(' (')[0]} · {info(base)[1]}"


def others(family: str, split: str) -> list[str]:
    """Arms on this bank that are not this page's centres: other lenses' arms and other studies' centres (rms)."""
    out = []
    for n in all_arms(family, split):
        a = catalog.parse(n)
        if a.readout != "rms" or n.startswith(("shuf.", "rand.")):
            continue
        if a.lens != "jlens":
            out.append(n)  # another reader: J++, the logit lens
        elif a.centre.split(":")[0] not in catalog.OPT_IN | {"zero", "fam", "tok"}:
            out.append(n)  # another study's centre (iteration's knnx8, u1rel, pco16, ...)
    return out
