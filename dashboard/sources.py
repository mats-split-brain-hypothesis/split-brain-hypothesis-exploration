"""Everything the dashboard shows, read from disk on load: the eval pipeline's outputs under
out/eval/<family>/<split>/ (summary, per-arm ranks, readouts and prompt-masked readouts, the model's own
next-token top 10, judge agreement), the analysis battery under out/analysis/<study>/, out/captures/
and the dev banks in data/dev/. Caches key on file mtimes, so a new evaluate or judge run shows up
on the next reload. ``JLM_DASH_OUT`` points the dashboard at another out/ (e.g. a test fixture).

Vocabulary view: every arm is read twice by evaluate.py, over the full vocabulary (``<arm>/*.jsonl``, the default) and
over the semantic vocabulary only (``<arm>/sem/*.jsonl``, J++'s Readout Filtering, ``jlm.controls.non_semantic_ids``).
Two sidebar switches (app.py) set ``vocab_mode()``: "jpp" moves the J++ arms to the semantic view, "all" every arm.
Every loader that takes an arm directory resolves it with ``view()``, so the pages switch without knowing; an arm
without ``sem/`` stays on its full readouts. Judge runs read the full readouts only, so a semantic arm has none.
"""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

import streamlit as st

import hfsync
from jlm import hfdata

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT, DEV = Path(os.environ.get("JLM_DASH_OUT") or REPO_ROOT / "out"), REPO_ROOT / "data" / "dev"
ON_SPACE = bool(os.environ.get("SPACE_ID"))  # the hosted dashboard (Hugging Face sets SPACE_ID in a Space)
EVAL, CAPTURES, ANALYSIS = OUT / "eval", OUT / "captures", OUT / "analysis"
STUDIES = REPO_ROOT / "notes" / "iteration-anthony" / "studies"
NEXT = "next-token"  # out/eval/<family>/<split>/next-token/readouts.jsonl: the model's own next-token top 10

#: The seven single-token families, in pipeline order, all evaluated end to end.
FAMILIES = ["typo", "association", "basic_readout", "multihop", "multilingual", "user_modeling", "directed_modulation"]
EVALUATED = FAMILIES
#: The multi-token families, kept separate: free score = distinctive-piece proxy (jlm.mtproxy); judged = the
#: bench's summarizer + regex. multilingual_multihop and multilingual_typo come later.
MT_FAMILIES = ["typo_mt", "multihop_mt", "basic_readout_mt", "multilingual_mt"]
ALL_FAMILIES = FAMILIES + MT_FAMILIES
#: Where strict match tracks the judge (experiments/report.py). On the other two, rank centres by judged runs.
STRICT_IS_PROXY = {"typo", "association", "basic_readout", "multihop", "multilingual"}
#: Fresh held-out dev splits authored after val was spent (S24, night-2): typo / association / multihop (val2b:
#: multihop / multilingual closed-answer subfamilies). Read once each; listed after val so pages that default to val
#: keep doing so.
FRESH = ["val2", "val3", "val2b"]
SPLITS = ["fit", "val", *FRESH, "bench"]
JUDGE = "judged-claude-haiku-5.5"
# Hand-picked typo/val cells where the plain lens reads letters and the centred one reads the word.
EXAMPLES = [("dev-ty-a-066", 44), ("dev-ty-a-028", 48), ("dev-ty-a-020", 48)]


def arm_dir(arm: str) -> str:
    return arm.replace("@", "-at-").replace("|", "__").replace(":", "~")


SEM = "sem"  # <arm>/sem/: the semantic-vocabulary readouts, ranks and masked top 10
MODES = ("full", "jpp", "all")


def vocab_mode() -> str:
    """The sidebar's vocabulary view: "full" (default), "jpp" (J++ arms semantic-only) or "all" (every arm)."""
    ss = st.session_state
    return "all" if ss.get("sem_all") else "jpp" if ss.get("sem_jpp") else "full"


def sem_applies(arm: str, mode: str | None = None) -> bool:
    """Whether ``mode`` reads this arm (name ``jpp:...`` or directory ``jpp~...``) over the semantic vocabulary."""
    mode = mode or vocab_mode()
    return mode == "all" or (mode == "jpp" and arm.startswith(("jpp:", "jpp~")))


def _resolve(family: str, split: str, adir: str, mode: str) -> str:
    if adir.endswith("/" + SEM) or not sem_applies(adir, mode) or adir == NEXT and mode != "all":
        return adir
    return f"{adir}/{SEM}" if _have(EVAL / family / split / adir / SEM / "readouts.jsonl") else adir


def view(family: str, split: str, adir: str) -> str:
    """The directory the current view reads for this arm: ``<adir>/sem`` when the view applies and it exists."""
    return _resolve(family, split, adir, vocab_mode())


def is_sem(family: str, split: str, adir: str) -> bool:
    return view(family, split, adir).endswith("/" + SEM)


def stamp() -> float:
    """Newest mtime among the files the dashboard reads; pass it to cached loaders. Fetches the bank summaries the
    shared dataset has and this out/ does not yet (small, and every results page starts from them)."""
    _get_many([*_glob(EVAL, "*/*/summary.json"), *_glob(EVAL, "*/*/forms.json")])  # forms.json: jlm.forms.SIDECAR
    files = [*EVAL.glob("*/*/summary.json"), *EVAL.glob("*/*/forms.json"), *EVAL.glob("*/*/*/agreement-*.json"), *EVAL.glob("*/*/*/judged*/results.json"),
             *CAPTURES.glob("*.pt"), *DEV.glob("*/*.json"), *ANALYSIS.glob("*/*"), *STUDIES.glob("*.md"), *STUDIES.glob("*.card.yaml")]
    return max((p.stat().st_mtime for p in files), default=0.0)


# ------------------------------------------------------------------ files here or in the shared dataset
# A restarted Space starts with an empty out/ and pulls the dataset in the background (hfsync), the large per-arm
# files last. So the pages list arms from local files plus the dataset's manifest (_have, _glob), and a read fetches
# a file the first time it is needed (_get): a page works from the first minute, whatever the pull has reached.


def _remote() -> dict[str, dict]:
    """The shared dataset's manifest (path relative to out/ -> {size, sha256, ...}); {} without one. jlm.hfdata keeps
    it for a few minutes, so this is cheap to call per file."""
    try:
        return hfdata.remote_files()
    except Exception:  # offline or unconfigured: local files only
        return {}


def _rel(p: Path) -> str | None:
    try:
        return p.relative_to(OUT).as_posix()
    except ValueError:
        return None


def _have(p: Path) -> bool:
    """``p`` is here, or the shared dataset has it (``_get`` fetches it)."""
    return p.exists() or _rel(p) in _remote()


def _glob(base: Path, pattern: str) -> list[Path]:
    """``base.glob(pattern)`` (``*`` within one path part) over local files and the shared dataset's."""
    found = set(base.glob(pattern))
    rb, parts = _rel(base), pattern.split("/")
    if rb is not None:
        pre = rb + "/" if rb else ""
        for r in _remote():
            if r.startswith(pre):
                rest = r[len(pre):].split("/")
                if len(rest) == len(parts) and all(fnmatch.fnmatchcase(x, y) for x, y in zip(rest, parts, strict=True)):
                    found.add(OUT / r)
    return sorted(found)


def _size(p: Path) -> int | None:
    """Size of ``p`` here, else in the shared dataset: the same on every machine, unlike an mtime, so a cache kept
    beside a file (``_sidecar``) is reused wherever the file is (or is not yet) downloaded."""
    return p.stat().st_size if p.exists() else (_remote().get(_rel(p)) or {}).get("size")


def _get(p: Path) -> Path:
    """``p``, downloaded from the shared dataset first when only the dataset has it."""
    if not p.exists() and (rel := _rel(p)) in _remote():
        with st.spinner(f"Fetching {rel} from the shared dataset…"):
            hfdata.ensure(rel, out=OUT)
    return p


def _get_many(paths) -> None:
    """Fetch those of ``paths`` only the shared dataset has, 32 at a time (each file is one request: one by one, a
    page that needs thousands of small files would wait minutes)."""
    from concurrent.futures import ThreadPoolExecutor

    rels = [r for p in paths if not p.exists() and (r := _rel(p)) in _remote()]
    if rels:
        with st.spinner(f"Fetching {len(rels)} files from the shared dataset…"), ThreadPoolExecutor(32) as ex:
            list(ex.map(lambda r: hfdata.ensure(r, out=OUT), rels))


def _jsonl(p: Path) -> list[dict]:
    p = _get(p)
    return [json.loads(line) for line in p.open()] if p.exists() else []


@lru_cache(maxsize=1)
def _byte_decoder() -> dict[str, int]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs, n = bs[:], 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {chr(c): b for b, c in zip(bs, cs, strict=True)}


def decode_token(tok: str) -> str:
    """Readable text for a byte-level BPE token ('å¸¸è§ģ' -> '常见'); plain text passes through."""
    dec = _byte_decoder()
    raw = b"".join(bytes([dec[ch]]) if ch in dec else ch.encode() for ch in tok)  # readouts keep plain spaces
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:  # a token that ends inside a multi-byte character
        return tok


def repo_state() -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""

    sha = git("rev-parse", "--short", "HEAD")
    if not sha:  # no checkout (the hosted dashboard): the build label tools/deploy_space.py sets, "branch@sha"
        branch, _, sha = os.environ.get("JLM_BUILD", "?@?").partition("@")
        return {"sha": sha, "branch": branch, "dirty": False}
    return {"sha": sha, "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


@st.cache_data(show_spinner=False)
def banks(_stamp: float) -> dict:
    """family -> {sizes: {fit, val, bench}, captured: {split: bool}}."""
    out = {}
    for f in ALL_FAMILIES:
        sizes = {s: len(json.loads(p.read_text())["items"]) for s in ("fit", "val") if (p := DEV / f / f"{s}.json").exists()}
        if (p := DEV / f / "candidates.json").exists():
            sizes["candidates"] = len(json.loads(p.read_text())["items"])
        if (p := EVAL / f / "bench" / "summary.json").exists():
            sizes["bench"] = json.loads(p.read_text())["result"]["n_items"]
        out[f] = {"sizes": sizes, "captured": {s: (CAPTURES / f"{f}-{s}.pt").exists() for s in SPLITS}}
    return out


def results(_stamp: float) -> dict:
    """family -> split -> {n_items, n_scored, excluded, layers, arms, diffs, by_layer}, in the current vocabulary view
    (each arm's ``sem`` flag says whether its numbers are semantic-only)."""
    return _results(_stamp, vocab_mode())


@st.cache_data(show_spinner="Reading out/eval…")
def _results(_stamp: float, mode: str) -> dict:
    from jlm import forms as jforms

    out = defaultdict(dict)
    for f in ALL_FAMILIES:
        for s in SPLITS:
            p = EVAL / f / s / "summary.json"
            if not p.exists():
                continue
            r = json.loads(p.read_text())["result"]
            jforms.fill_from_sidecar(p.parent, r)  # strict + forms fields a run on an older branch stripped from the summary
            sem = {a for a, v in r["arms"].items() if "sem" in v and sem_applies(a, mode)}
            if "scored_ids" not in r:  # written before the pipeline's summary format (early x-runs): not readable here
                continue
            # masked / echo / next: the control suite (evaluate.py since 90e65e8); None on older arms
            arms = {a: {"v": v["strict"]["value"], "ci": v["strict"]["ci95"], "n": v["strict"]["n"],
                        "rank": v["median_best_rank"], "masked": (v.get("strict_masked") or {}).get("value"),
                        "echo": v.get("echo"), "next": v.get("next_overlap"), "sem": a in sem}
                    for a, v in ((a, v["sem"] if a in sem else v) for a, v in r["arms"].items())}
            diffs = {}
            for k, v in r["diffs"].items():  # a diff of two semantic arms comes from diffs_sem; mixed views have none
                a, _, b = k.partition(" - ")
                if (a in sem) != (b in sem):
                    continue
                v = r.get("diffs_sem", {}).get(k) if a in sem else v
                if v is not None:
                    diffs[k] = {"d": v["diff"], "ci": v["ci95"]}
            # strict + forms (jlm.forms; single-token families, after evaluate.py --rescore): the sem view's own rate
            forms = {a: (fb.get("sem") if a in sem else fb.get("strict"))
                     for a, fb in ((a, v.get("forms") or {}) for a, v in r["arms"].items())}
            for a, fv in forms.items():
                arms[a]["forms"] = {"v": fv["value"], "ci": fv["ci95"], "n": fv["n"]} if fv and fv.get("value") is not None else None
            diffs_forms = {k: {"d": v["diff"], "ci": v["ci95"]} for k, v in r.get("diffs_forms", {}).items()
                           if v.get("diff") is not None and not set(k.split(" - ")) & sem}
            nt = (r.get("next_token_sem") if mode == "all" else None) or r.get("next_token") or {}
            out[f][s] = {"scorer": r.get("scorer", "strict (jle x89)"), "n_items": r["n_items"], "n_scored": r["n_scored"], "excluded": r.get("excluded", {}),
                         "layers": r["layers"], "arms": arms, "diffs": diffs, "scored_ids": r["scored_ids"],
                         "diffs_forms": diffs_forms, "forms_ids": (r.get("forms") or {}).get("scored_ids"),
                         "next_token": {"v": (nt.get("strict") or {}).get("value"), "echo": nt.get("echo")} if nt else None,
                         "by_layer": _by_layer(f, s, r["layers"], set(r["scored_ids"]), list(arms), mode)}
    return dict(out)


def _by_layer(family: str, split: str, layers: list[int], scored: set[str], arms: list[str], mode: str) -> dict:
    """Share of scored items whose best target is in the top 10 at each layer (rank < 10)."""
    out = {}
    for a in arms:
        p = EVAL / family / split / _resolve(family, split, arm_dir(a), mode) / "ranks.jsonl"
        if (curve := _arm_by_layer(p, tuple(layers), tuple(sorted(scored)), _mt(p))) is not None:
            out[a] = curve
    return out


@lru_cache(maxsize=256)
def _bank_cache(side: Path, _mtime: float) -> dict:
    try:
        return json.loads(side.read_text())
    except (OSError, ValueError):
        return {}


def _sidecar(src: Path, name: str, key_parts, compute):
    """``compute()`` for the arm that ``src`` (a file under out/eval/<family>/<split>/<arm>/) belongs to, kept in one
    JSON file per bank, ``out/eval/<family>/<split>/<name>`` ({arm: {key, value}}), under a key built from
    ``key_parts`` (the source file's size and the arguments): read back while the key matches, recomputed and written
    back when it does not. For derived numbers that are slow to rebuild and should survive a restart. One file per
    bank, not per arm: a fresh Space fetches tens of these, not thousands (the Hub allows about 5,000 downloads per
    5 minutes)."""
    parts = src.relative_to(EVAL).parts
    side, arm = EVAL / parts[0] / parts[1] / name, "/".join(parts[2:-1])
    key = hashlib.md5(json.dumps(key_parts).encode()).hexdigest()
    hit = _bank_cache(side, _mt(_get(side))).get(arm)
    if hit and hit.get("key") == key and "value" in hit:
        return hit["value"]
    value = compute()
    try:
        data = {**_bank_cache(side, _mt(side)), arm: {"key": key, "value": value}}
        tmp = side.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(side)
    except OSError:
        pass
    return value


@st.cache_data(show_spinner=False, max_entries=8192)
def _arm_by_layer(p: Path, layers: tuple[int, ...], scored: tuple[str, ...], _mtime: float) -> list[float] | None:
    """One arm's pass-by-layer curve. The ranks files total about 1 GB, and parsing all of them whenever anything in
    out/ changed made every page that reads results() wait ~15 s; so each curve is also kept next to its ranks.jsonl
    (``bank.by_layer.json``, one per bank) and only a new or rewritten arm is parsed again."""

    def compute():
        best = defaultdict(lambda: 10**9)
        ok = set(scored)
        if _get(p).exists():
            for line in p.open():
                r = json.loads(line)
                if r["id"] in ok and r.get("rank") is not None and r["rank"] >= 0:  # -1: no single-token target
                    best[r["id"], r["layer"]] = min(best[r["id"], r["layer"]], r["rank"])
        return [sum(best[i, L] < 10 for i in scored) / len(scored) for L in layers] if best else None

    return _sidecar(p, "bank.by_layer.json", [_size(p), layers, scored], compute)


@st.cache_data(show_spinner=False)
def agreement(_stamp: float) -> dict:
    """family -> arm -> strict vs judge on val (experiments/agreement.py output), from any judge run."""
    out = defaultdict(dict)
    for f in ALL_FAMILIES:
        for p in sorted((EVAL / f / "val").glob("*/agreement-*.json")):
            r = json.loads(p.read_text())["result"]
            out[f][r["arm"]] = {"run": run_label(p.stem.removeprefix("agreement-")),
                                "strict": r["strict"]["value"], "judge": r["judge"]["value"], "n": r["n_items"],
                                "k_items": r["items"]["kappa"], "k_cells": r["cells"]["kappa"],
                                "strict_only": r["items"]["table"].get("strict=1,judge=0", 0)}
    return dict(out)


@st.cache_data(show_spinner=False)
def examples(_stamp: float) -> list[dict]:
    """The EXAMPLES cells read plain (zero|cos) and centred (fam@fit|cos)."""
    bank = {i["name"]: i for i in json.loads((DEV / "typo" / "val.json").read_text())["items"]}
    arms = ("zero|cos", "fam@fit|cos")
    rows = {a: {(r["id"], r["layer"]): r for r in _jsonl(EVAL / "typo" / "val" / arm_dir(a) / "readouts.jsonl")} for a in arms}
    ranks = {a: {(r["id"], r["layer"]): r["rank"] for r in _jsonl(EVAL / "typo" / "val" / arm_dir(a) / "ranks.jsonl")} for a in arms}
    out = []
    for k in EXAMPLES:
        if k not in rows["zero|cos"] or k not in rows["fam@fit|cos"]:
            continue
        it = bank[k[0]]
        out.append({"id": k[0], "layer": k[1], "prompt": it["prompt"], "typo": it["typo"], "target": it["intermediates"][0],
                    "read": decode_token(rows["zero|cos"][k]["token"]),
                    "zero": [decode_token(t) for t in rows["zero|cos"][k]["tokens"]],
                    "fam": [decode_token(t) for t in rows["fam@fit|cos"][k]["tokens"]],
                    "rank_zero": ranks["zero|cos"].get(k), "rank_fam": ranks["fam@fit|cos"].get(k)})
    return out


# ------------------------------------------------------------------ explorer: one bank, cell by cell


def _mt(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def splits_with_readouts(family: str) -> list[str]:
    return [s for s in SPLITS if _glob(EVAL / family / s, "*/readouts.jsonl")]


def families_with_readouts() -> list[str]:
    have = {p.parts[-4] for p in _glob(EVAL, "*/*/*/readouts.jsonl")}
    return [f for f in ALL_FAMILIES if f in have] + sorted(have - set(ALL_FAMILIES))


def arm_dirs(family: str, split: str) -> list[str]:
    """Directory names of the arms with readouts for this bank (``fam-at-fit__cos``); not the next-token baseline."""
    return sorted(p.parent.name for p in _glob(EVAL / family / split, "*/readouts.jsonl") if p.parent.name != NEXT)


def readouts_mtime(family: str, split: str, adir: str, kind: str = "readouts") -> float:
    return _mt(EVAL / family / split / view(family, split, adir) / f"{kind}.jsonl")


def has_masked(family: str, split: str, adir: str) -> bool:
    """Whether the arm has its prompt-masked top 10 (masked.jsonl, jlm.controls; evaluate.py since 90e65e8)."""
    return _have(EVAL / family / split / view(family, split, adir) / "masked.jsonl")


def cells(family: str, split: str, adir: str, _mtime: float, kind: str = "readouts") -> dict[tuple[str, int, int], dict]:
    """(item, layer, pos) -> {token, tokens, scores} for one arm, tokens kept raw (the scorer's strings).
    ``kind="masked"``: the top 10 after the item's prompt-content forms are removed from the vocabulary."""
    return _cells(family, split, view(family, split, adir), _mtime, kind)


@st.cache_data(show_spinner="Loading readouts…", max_entries=96)
def _cells(family: str, split: str, adir: str, _mtime: float, kind: str = "readouts") -> dict[tuple[str, int, int], dict]:
    out = {}
    for r in _jsonl(EVAL / family / split / adir / f"{kind}.jsonl"):
        out[r["id"], r["layer"], r["pos"]] = {"token": r.get("token", ""), "tokens": r["tokens"], "scores": r.get("scores", [])}
    return out


def ranks(family: str, split: str, adir: str, _mtime: float) -> dict[tuple[str, int, int], int]:
    """(item, layer, pos) -> best rank of an accepted target in the arm's vocabulary view (-1: no single-token target)."""
    return _ranks(family, split, view(family, split, adir), _mtime)


@st.cache_data(show_spinner=False, max_entries=64)
def _ranks(family: str, split: str, adir: str, _mtime: float) -> dict[tuple[str, int, int], int]:
    return {(r["id"], r["layer"], r["pos"]): r["rank"] for r in _jsonl(EVAL / family / split / adir / "ranks.jsonl")}


@st.cache_data(show_spinner="Loading the bank…")
def bank(family: str, split: str) -> dict:
    """Items, read specs and accepted target forms for one bank, via the pipeline's own loaders. ``extra``: per item,
    the other forms strict + forms also accepts (jlm.forms; empty on the multi-token families)."""
    from jlm import banks as jbanks
    from jlm import forms as jforms
    from jlm import score as jscore

    b = jbanks.load(family, split)
    try:
        specs = {s.id: s.row() for s in jbanks.specs(b)}
    except Exception:  # a family whose planner needs more than the bank (render it from the item instead)
        specs = {}
    summ = EVAL / family / split / "summary.json"
    scored = set(json.loads(summ.read_text())["result"]["scored_ids"]) if _get(summ).exists() else None
    if family in MT_FAMILIES:  # the piece proxy's accepted tokens (exact display strings), per item
        from wsbench.produce.render import display_tokens

        from jlm import mtproxy

        tok = tokenizer()
        units = mtproxy.units_of(b, tok, lambda ids: display_tokens(tok, ids)) if tok is not None else {}
        forms = {i: sorted({p for u in us for p in u.pieces}) for i, us in units.items()}
        extra = {}
    else:
        units = None
        forms = {i: sorted(jscore.accepted_forms(it)) for i, it in b.by_id().items()}
        table = jforms.table(family)
        extra = {i: sorted(jscore.accepted_forms(it, table) - set(forms[i])) for i, it in b.by_id().items()}
    return {"items": b.by_id(), "specs": specs, "forms": forms, "extra": extra, "units": units,
            "targets": {i: jbanks.targets(it) for i, it in b.by_id().items()}, "scored": scored}


def normalise(tok: str) -> str:
    """The strict scorer's token normalisation (jlm.score.normalise)."""
    return tok.removeprefix(" ").casefold()


def is_hit(family: str, tok: str, forms) -> bool:
    """Whether a readout token credits the item: strict normalised equality, or for the multi-token
    families an exact distinctive piece (jlm.mtproxy). A piece hit is weaker evidence than a form."""
    return tok in forms if family in MT_FAMILIES else normalise(tok) in forms


def is_form_hit(family: str, tok: str, extra) -> bool:
    """Whether a readout token is one of the item's other forms (``bank()["extra"]``): it credits the item under
    strict + forms only (``swims`` for ``swimming``). Never on the multi-token families."""
    return family not in MT_FAMILIES and normalise(tok) in extra


def hit_kind(family: str, tok: str, forms, extra) -> str:
    """CSS class for a readout token: "hit" (the target), "formhit" (another form of it) or ""."""
    return "hit" if is_hit(family, tok, forms) else "formhit" if is_form_hit(family, tok, extra) else ""


def hit_cells(family: str, split: str, adir: str, _mtime: float, kind: str = "readouts",
              with_forms: bool = False) -> dict[str, list[tuple[int, int]]]:
    """Item -> the (layer, pos) cells whose top 10 holds an accepted target (strict rule; ``with_forms``: or one
    of its other forms, strict + forms)."""
    return _hit_cells(family, split, view(family, split, adir), _mtime, kind, with_forms)


@st.cache_data(show_spinner=False, max_entries=96)
def _hit_cells(family: str, split: str, adir: str, _mtime: float, kind: str = "readouts",
               with_forms: bool = False) -> dict[str, list[tuple[int, int]]]:
    b = bank(family, split)
    forms = {i: set(f) | (set(b["extra"].get(i, ())) if with_forms else set()) for i, f in b["forms"].items()}
    out: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for (i, L, p), r in _cells(family, split, adir, _mtime, kind).items():
        if any(is_hit(family, t, forms.get(i, ())) for t in r["tokens"]):
            out[i].append((L, p))
    return {i: sorted(v) for i, v in out.items()}


MODEL, MODEL_REVISION = "Qwen/Qwen3.6-27B", "6a9e13bd6fc8f0983b9b99948120bc37f49c13e9"  # the captures' pin


@st.cache_resource(show_spinner="Loading the tokenizer…")
def tokenizer():
    """The model's tokenizer, from the local HF cache or else the Hub (None if neither works)."""
    try:
        from transformers import AutoTokenizer

        try:
            return AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, local_files_only=True)
        except OSError:  # not cached here (a hosted dashboard): fetch the tokenizer files only, a few MB
            return AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION)
    except Exception:
        return None


@st.cache_data(show_spinner=False, max_entries=512)
def rendered(family: str, split: str, item: str) -> list[str] | None:
    """The item's prompt as the model read it, one decoded string per token (the bench's own render), so a
    read position indexes straight into it. None when the tokenizer or the read spec is unavailable."""
    from wsbench.produce.render import render
    from wsbench.readplan import ReadSpec

    tok, spec = tokenizer(), bank(family, split)["specs"].get(item)
    if tok is None or spec is None:
        return None
    return render(ReadSpec(**spec), tok).decoded


# ------------------------------------------------------------------ judge runs (experiments/judge.py)


def run_label(run: str) -> str:
    """``judged-claude-haiku-5.5-L24-36-48-60`` -> ``Haiku 5.5 · L24/36/48/60``; ``judged`` -> the pinned judge."""
    if run == "judged":
        return "pinned judge"
    rest = run.removeprefix("judged-")
    model, _, layers = rest.partition("-L")
    name = {"claude-haiku-5.5": "Haiku 5.5"}.get(model, model)
    return name + (f" · L{layers.replace('-', '/')}" if layers else " · all layers")


def judge_runs(family: str, split: str, adir: str) -> list[str]:
    """Full judge runs for one arm, newest first (smoke runs, ``*-limitN``, left out). None in the semantic view:
    the judge read the full-vocabulary readouts."""
    runs = [p.parent for p in (EVAL / family / split / view(family, split, adir)).glob("judged*/results.json") if "-limit" not in p.parent.name]
    return [p.name for p in sorted(runs, key=lambda p: -_mt(p / "results.json"))]


@st.cache_data(show_spinner=False, max_entries=128)
def judged(family: str, split: str, adir: str, run: str, _mtime: float) -> dict:
    """One judge run, normalised: headline rate, and per item its pass plus per-cell verdicts keyed
    (layer, pos) (pos None for the bank-judge families, which judge one cell per layer). The cell rule is
    experiments/agreement.py's: user_modeling passes on gold picked as inferred_characterization,
    directed_modulation on gold picked as content_bound."""
    r = json.loads((EVAL / family / split / adir / run / "results.json").read_text())
    items: dict[str, dict] = {}
    rows = r.get("rows", [])
    if rows and "pass" in rows[0]:  # bank-judge families
        for x in rows:
            cells = {(int(L), None): {"pass": bool(v.get("expressed")), "evidence": v.get("quote", ""), "why": ""}
                     for L, v in (x.get("layers") or {}).items()}
            items[x["id"]] = {"pass": bool(x["pass"]), "cells": cells}
    else:
        basis = "content_bound" if family == "directed_modulation" else "inferred_characterization"
        for x in rows:
            i = x.get("item") or x.get("id")
            it = items.setdefault(i, {"pass": False, "cells": {}})
            hit = x.get("pick") == "gold" and x.get("basis") == basis
            it["pass"] |= hit
            what = x.get("pick", "")
            if what == "gold" and not hit:
                what = f"gold, as {x.get('basis', '').replace('_', ' ')}"
            it["cells"][x["layer"], x["pos"]] = {"pass": hit, "pick": what.replace("_", " "),
                                                 "evidence": x.get("evidence", ""), "why": x.get("rationale", "")}
    n = r.get("numbers", {})
    return {"label": run_label(run), "value": n.get("value"), "ci": n.get("ci95"), "n": r.get("n_items"),
            "layers": (r.get("config") or {}).get("layers"), "pinned": r.get("pinned_instrument", False), "items": items}


# ------------------------------------------------------------------ geometry of h - mu (jlm.geometry, from the captures)


def captures_mtime(family: str, split: str, ref: str = "") -> float:
    """Newest mtime of the read bank's capture and its centre's reference capture (cache key). Fetches them from the
    shared dataset first when they are not here (hfsync)."""
    hfsync.need_captures(family, split, "", ref)
    return max(_mt(CAPTURES / f"{family}-{split}.pt"), _mt(CAPTURES / f"{family}-{ref}.pt") if ref not in ("", "self") else 0.0,
               _mt(DEV / family / f"{split}.json"))


def _jfit(family: str, split: str, centre: str, ref: str):
    """``jlm.geometry.fit``, fetching from the shared dataset any capture it finds missing and trying again: a centre
    may read other families' captures (knnx8 and the k-means centres pool every family's fit cells), which
    ``hfsync.need_captures`` cannot know in advance."""
    from jlm import geometry as jgeo

    tried: set[str] = set()
    while True:
        try:
            return jgeo.fit(family, split, centre, ref)
        except FileNotFoundError as e:
            m = re.search(r"no capture at (\S+?);", str(e))
            if not m:
                raise
            p = Path(m.group(1))
            rel = p.relative_to(p.parents[1]).as_posix()  # <out>/captures/<name>.pt -> captures/<name>.pt
            if rel in tried:
                raise
            tried.add(rel)
            with st.spinner(f"Fetching {rel} from the shared dataset…"):
                if hfdata.ensure(rel, out=p.parents[1]) is None:
                    raise


@st.cache_data(show_spinner="Centring the captured states…", max_entries=64)
def geometry(family: str, split: str, centre: str, ref: str, _mtime: float) -> dict[tuple[str, int, int], dict]:
    """(item, layer, pos) -> {norm_h, norm_mu, norm_x, cos, support, fallback, token} for arm centre@ref; mu is
    rebuilt from the captures with jlm.centres exactly as the evaluated arm built it (no lens needed)."""
    from jlm import geometry as jgeo

    hfsync.need_captures(family, split, centre, ref)  # the centre's own reference files
    rows = jgeo.cell_stats(_jfit(family, split, centre, ref))
    return {(r["id"], r["layer"], r["pos"]): r for r in rows}


@st.cache_data(show_spinner="Loading the captured states…", max_entries=16)
def states(family: str, split: str, layer: int, _mtime: float) -> dict:
    """The bank's read-cell states at one layer: {cells: [(item, pos, token)], H: [n, d] float32}."""

    cells, H, _ = _jfit(family, split, "zero", "").layer(layer)
    return {"cells": [(c.item, c.pos, c.token) for c in cells], "H": H.numpy()}


@st.cache_data(show_spinner="Centring the captured states…", max_entries=32)
def centres_at(family: str, split: str, centre: str, ref: str, layer: int, _mtime: float) -> dict:
    """Arm centre@ref's mu at each read cell of one layer, in states()'s cell order: {MU: [n, d], support: [n]}."""

    hfsync.need_captures(family, split, centre, ref)  # the centre's own reference files
    f = _jfit(family, split, centre, ref)
    cells, _, MU = f.layer(layer)
    return {"MU": MU.numpy(), "support": [f.centre.support(c)[0] for c in cells]}


def has_members(centre: str) -> bool:
    """Whether a centre can say which reference cells it averages for a cell (jlm.centres' optional members())."""
    from jlm import centres

    try:
        return hasattr(centres.make(centre), "members")
    except KeyError:
        return False


@st.cache_data(show_spinner="Projecting the reference cells…", max_entries=24)
def cell_cloud(family: str, split: str, layer: int, item: str, pos: int, pool_arm: tuple[str, str],
               arm_keys: tuple, axes: str, _mt: float) -> dict:
    """One read cell against the reference cells of pool_arm's centre (its members() pool; the family's reference
    cells, as fam@ref builds them, for a centre without one), in 3 principal directions: the pool's ("pool"), or
    those of the cells around this read ("cell": its members, h and every arm's mu). Returns the projected pool with
    (group, family, token) per row, the rows averaged into pool_arm's mu here (None when the centre does not say),
    the cell's own-group rows (never in mu), h, each arm's mu, the origin, the shares and each member's cos(h, .).
    The rows are checked against the arm's mu at this cell: when their mean is not mu they are dropped (``why``)."""
    import torch

    from jlm import centres
    from jlm import geometry as jgeo

    centre, ref = pool_arm
    f = _jfit(family, split, centre, ref)
    c = f.centre if hasattr(f.centre, "members") else None
    src = c or _jfit(family, split, "fam", ref).centre
    X, meta = src.reference(layer)
    s = states(family, split, layer, captures_mtime(family, split))
    j = next(k for k, (i, p, _) in enumerate(s["cells"]) if i == item and p == pos)
    h = torch.from_numpy(s["H"][j])
    mus = {ak: torch.from_numpy(centres_at(family, split, *ak, layer, captures_mtime(family, split, ak[1]))["MU"][j])
           for ak in arm_keys}
    cell = next(x for x in centres.cell_refs([it for it in f.items if it.id == item], family, layer, f.groups) if x.pos == pos)
    members, why = None, "" if c is not None else "it does not say which reference cells it averages"
    if c is not None:
        members = c.members(centres.Batch(layer, [cell], h[None], {it.id: it for it in f.items}))[0]
        mu = mus.get(pool_arm)
        if mu is not None and len(members) and (X[members].double().mean(0) - mu.double()).norm() > 1e-3 * mu.double().norm():
            members, why = None, "its μ here is not the plain mean of the cells it picks"  # e.g. a subclass that reweights
    own = [k for k, (g, _, _) in enumerate(meta) if g == cell.group]
    if axes == "cell" and members is not None and len(members):
        basis, origin, share = jgeo.pca(torch.cat([X[members], h[None], *(m[None] for m in mus.values())]), 3)
    else:
        basis, origin, share = jgeo.pca(X, 3)
    P = lambda Y: jgeo.project(Y, basis, origin).numpy()  # noqa: E731
    cos = (torch.nn.functional.cosine_similarity(X[members], h[None]).numpy() if members is not None and len(members) else None)
    return {"pool": P(X), "meta": meta, "members": None if members is None else members.numpy(), "own": own,
            "h": P(h[None])[0], "mu": {ak: P(m[None])[0] for ak, m in mus.items()},
            "origin": P(torch.zeros(1, X.shape[1]))[0], "share": share.numpy(), "cos": cos, "named": members is not None,
            "why": why}


# ------------------------------------------------------------------ tracked tokens: the lens read live at one cell
# The pipeline stores each cell's top 10 and the best accepted target's rank only, so the place of any other token
# (or of a multi-token target's first piece) is read here from the captures, the centre and the lens, as jlm.read
# does. W_U stays bf16 (2.5 GB, scored in fp32 chunks); J is memory-mapped; the cos denominators come from
# out/lens (written by evaluate.py). Ranks agree with ranks.jsonl to within float rounding (off by 1-2 above #100k).


@st.cache_resource(show_spinner="Loading the unembedding (once per server, about 2.5 GB)…")
def _unembed() -> dict:
    import torch

    from jlm import lens as jl

    dev = "mps" if torch.backends.mps.is_available() else "cpu"  # Apple GPU: the vocabulary product in 0.3 s, not 2-3 s
    return {"w_u": jl._model_tensor("lm_head.weight").to(dev), "dev": dev,
            "gain": 1 + jl._model_tensor("language_model.norm.weight").float()}


@st.cache_resource(show_spinner="Fitting the centre…", max_entries=48)
def _fitted(family: str, split: str, centre: str, ref: str, _mt: float):

    return _jfit(family, split, centre, ref)


@st.cache_resource(show_spinner="Mapping the lens…")
def _jac(name: str):
    import torch
    from huggingface_hub import hf_hub_download
    from umot.provenance import PINS

    from jlm import lens as jl

    repo, file = jl.LENSES[name]
    obj = torch.load(hf_hub_download(repo, file, revision=PINS[repo]), map_location="cpu", weights_only=False, mmap=True)
    obj = obj.get("parameters", obj)
    jac = obj["J"] if "J" in obj else obj["jacobians"]
    return (lambda L: jac[L] if L in jac else jac[str(L)]) if isinstance(jac, dict) else jac.__getitem__


@st.cache_resource(show_spinner=False)
def vocab() -> dict:
    """{display: [id -> display string as readouts show it], ids: display string -> first id}; None without a tokenizer."""
    from wsbench.produce.render import display_tokens

    tok = tokenizer()
    if tok is None:
        return None
    disp = display_tokens(tok, list(range(_unembed()["w_u"].shape[0])))
    ids: dict[str, int] = {}
    for i, t in enumerate(disp):
        ids.setdefault(t, i)
    return {"display": disp, "ids": ids}


@st.cache_resource(show_spinner="Listing the non-semantic tokens…", max_entries=16)
def non_semantic(family: str, split: str):
    """The ids the semantic view removes for this bank, as evaluate.py removes them (jlm.controls.non_semantic_ids,
    the bank's accepted ids spared): a bool mask [V]."""
    import torch

    from jlm import banks as jbanks
    from jlm import controls
    from jlm import score as jscore

    B, V = bank(family, split), vocab()
    if B["units"] is not None:
        spared = {t for us in B["units"].values() for u in us for t in u.ids}
    else:
        spared = {t for ts in jscore.accepted_ids(V["display"], jbanks.load(family, split)).values() for t in ts}
    mask = torch.zeros(len(V["display"]), dtype=torch.bool)
    mask[controls.non_semantic_ids(tokenizer(), len(V["display"]), spared)] = True
    return mask


def pieces(word: str) -> list[str]:
    """How the model's tokenizer splits ``word`` (display strings, as readouts show them)."""
    from wsbench.produce.render import display_tokens

    tok = tokenizer()
    return [] if tok is None else display_tokens(tok, tok.encode(word, add_special_tokens=False))


@st.cache_resource(show_spinner="Reading this cell through the lens at every layer…", max_entries=4)
def cell_scores(family: str, split: str, item: str, pos: int, arms: tuple[tuple[str, str, str, str], ...],
                layers: tuple[int, ...], _mt: float) -> dict:
    """Full-vocabulary readout scores of one read cell for each arm (centre, ref, readout, lens) at each layer:
    {S: [V, n] float32, cols: [(arm, layer)], skipped: {arm: why}}. Arms whose centre cannot be rebuilt here
    (e.g. a centre that needs the context captures) are skipped with the reason."""
    import torch
    from umot.provenance import PINS

    from jlm import centres
    from jlm import lens as jl

    U = _unembed()
    X, cols, skipped = {}, [], {}
    for arm in arms:
        centre, ref, readout, lname = arm
        try:
            f = _fitted(family, split, centre, ref, captures_mtime(family, split, ref))
            by_id = {it.id: it for it in f.items}
            for L in layers:
                if centre.partition(".")[0] in centres.CONTROLS:  # shuf. / rand. take g from other cells: the whole layer
                    cells, H, MU = f.layer(L)
                    j = next(k for k, c in enumerate(cells) if c.item == item and c.pos == pos)
                    X[arm, L] = H[j] - MU[j]
                    continue
                # other centres give each cell's g from the reference set alone: this item's cells suffice (same g)
                cells = [c for c in centres.cell_refs([by_id[item]], family, L, f.groups) if c.pos == pos]
                H = torch.stack([by_id[item].acts[L][c.i].float() for c in cells])
                X[arm, L] = centres.apply(f.centre, centres.Batch(L, cells, H, by_id))[0]
        except Exception as e:  # noqa: BLE001 (shown to the reader)
            skipped[arm] = f"{type(e).__name__}: {e}"
            X = {k: v for k, v in X.items() if k[0] != arm}
    Z, den = [], []
    for (arm, L), x in X.items():
        readout, lname = arm[2], arm[3]
        z = _jac(lname)(L).float() @ x
        if readout == "rms":
            z = U["gain"] * z / torch.sqrt(z.square().mean() + jl.RMS_EPS)
            den.append(None)
        else:
            name = f"cos-denom-{PINS[jl.LENSES[lname][0]][:8]}-L{L:03d}.pt"
            p = OUT / "lens" / name if (OUT / "lens" / name).exists() else jl.DENOM_CACHE / name
            den.append(torch.load(p))
        Z.append(z)
        cols.append((arm, L))
    if not cols:
        return {"S": None, "cols": [], "skipped": skipped}
    w_u, Zm = U["w_u"], torch.stack(Z, 1).to(U["dev"])
    S = torch.cat([w_u[i : i + 65536].float() @ Zm for i in range(0, w_u.shape[0], 65536)])
    for k, d in enumerate(den):
        if d is not None:
            S[:, k] /= d.to(S.device)
    # each column sorted once, so a token's place is a binary search (token_places), not a pass over the vocabulary;
    # once over the full vocabulary and once over the semantic one (the vocabulary view)
    S = S.cpu()
    sem = ~non_semantic(family, split)[: S.shape[0]]
    return {"S": S, "asc": S.T.contiguous().sort(1).values, "asc_sem": S[sem].T.contiguous().sort(1).values,
            "sem": sem, "cols": cols, "skipped": skipped}


def token_places(cs: dict, token_id: int) -> dict[tuple, int]:
    """(arm, layer) -> 0-based place of one token in the arm's readout (tokens scoring strictly higher), over the
    vocabulary the current view reads for that arm. In the semantic view a non-semantic token has no place."""
    import torch

    if cs["S"] is None:
        return {}
    v = cs["S"][token_id]
    out = {}
    for key in ("asc", "asc_sem"):
        semantic = key == "asc_sem"
        idx = [k for k, (arm, _L) in enumerate(cs["cols"]) if sem_applies("jpp:" if arm[3] == "jpp" else "", None) == semantic]
        if not idx or (semantic and not cs["sem"][token_id]):
            continue
        A = cs[key][idx]
        higher = A.shape[1] - torch.searchsorted(A, v[idx][:, None].contiguous(), right=True)[:, 0]
        out |= dict(zip([cs["cols"][k] for k in idx], higher.tolist(), strict=True))
    return out


# ------------------------------------------------------------------ controls (jlm.controls): echo, masked, next token


@st.cache_data(show_spinner="Rendering the prompts…", max_entries=32)
def prompt_forms(family: str, split: str) -> dict[str, frozenset[str]]:
    """Item -> its prompt-content forms, as jlm.controls.prompt_forms builds them for the echo control (each item's
    render as display tokens; forms in half the bank's renders, i.e. the template, left out). Empty without the
    tokenizer or the read specs."""
    from wsbench.produce.render import render
    from wsbench.readplan import ReadSpec

    from jlm import controls

    tok, specs = tokenizer(), bank(family, split)["specs"]
    if tok is None or not specs:
        return {}
    return controls.prompt_forms({i: render(ReadSpec(**sp), tok).tokens for i, sp in specs.items()})


def is_echo(tok: str, forms) -> bool:
    """Whether a readout token is one of the item's prompt forms (jlm.controls.echo's rule)."""
    return normalise(tok).strip() in forms


def next_tokens(family: str, split: str, _mtime: float) -> dict[tuple[str, int], dict]:
    """(item, pos) -> the model's own next-token top 10 at the read cell {layer, token, tokens, scores}; {} if absent.
    Over the semantic vocabulary when every arm is (vocab_mode "all")."""
    return _next_tokens(family, split, view(family, split, NEXT), _mtime)


@st.cache_data(show_spinner=False, max_entries=32)
def _next_tokens(family: str, split: str, ndir: str, _mtime: float) -> dict[tuple[str, int], dict]:
    return {(r["id"], r["pos"]): r for r in _jsonl(EVAL / family / split / ndir / "readouts.jsonl")}


def next_mtime(family: str, split: str) -> float:
    return _mt(EVAL / family / split / view(family, split, NEXT) / "readouts.jsonl")


# ------------------------------------------------------------------ full vs semantic vocabulary, side by side (Semantic page)


@st.cache_data(show_spinner="Reading both vocabulary views…")
def vocab_compare(_stamp: float) -> dict:
    """family -> split -> {n_scored, semantic (the filter's counts), arms: {arm: {full, sem}}, diffs, diffs_sem,
    next, next_sem}: each arm's strict pass {v, ci} and median best rank in both views, read from summary.json
    whatever the sidebar's view. Arms without a ``sem`` block have sem None."""
    def strict(v):
        return None if not v else {"v": v["strict"]["value"], "ci": v["strict"]["ci95"], "rank": v.get("median_best_rank"),
                                   "masked": (v.get("strict_masked") or {}).get("value")}

    out = defaultdict(dict)
    for p in EVAL.glob("*/*/summary.json"):
        f, sp = p.parts[-3], p.parts[-2]
        r = json.loads(p.read_text())["result"]
        d = lambda m: {k: {"d": v["diff"], "ci": v["ci95"]} for k, v in (m or {}).items() if v.get("diff") is not None}  # noqa: E731
        out[f][sp] = {"n_scored": r["n_scored"], "semantic": r.get("semantic"),
                      "arms": {a: {"full": strict(v), "sem": strict(v.get("sem"))} for a, v in r["arms"].items()},
                      "diffs": d(r.get("diffs")), "diffs_sem": d(r.get("diffs_sem")),
                      "next": ((r.get("next_token") or {}).get("strict") or {}).get("value"),
                      "next_sem": ((r.get("next_token_sem") or {}).get("strict") or {}).get("value")}
    return dict(out)


def is_semantic_token(tok: str) -> bool:
    """J++'s rule on a readout token's text: it has a letter or a digit."""
    return any(ch.isalnum() for ch in tok)


@st.cache_data(show_spinner=False, max_entries=256)
def junk_by_layer(family: str, split: str, adir: str, _mtime: float) -> dict:
    """{layers, share: mean share of the top 10 that is non-semantic per layer, top: the commonest such tokens} over
    one arm's full-vocabulary readouts (kept per bank, ``bank.junk_by_layer.json``)."""
    p = EVAL / family / split / adir / "readouts.jsonl"

    def compute():
        acc, top = defaultdict(lambda: [0, 0]), defaultdict(int)
        for r in _jsonl(p):
            bad = [t for t in r["tokens"] if not is_semantic_token(t)]
            a = acc[r["layer"]]
            a[0] += len(bad)
            a[1] += len(r["tokens"])
            for t in bad:
                top[t] += 1
        layers = sorted(acc)
        return {"layers": layers, "share": [acc[L][0] / max(1, acc[L][1]) for L in layers],
                "top": sorted(top.items(), key=lambda kv: -kv[1])[:12]}

    return _sidecar(p, "bank.junk_by_layer.json", [_size(p)], compute)


@st.cache_data(show_spinner=False)
def sem_refits(_stamp: float) -> list[dict]:
    """Arms whose semantic readouts were backfilled from a refit that does not reproduce the stored full readouts
    (sem/provenance.json refit_differs_from_stored > 0): {family, split, arm dir, share}."""
    out = []
    for p in EVAL.glob(f"*/*/*/{SEM}/provenance.json"):
        share = (json.loads(p.read_text()).get("result") or {}).get("refit_differs_from_stored")
        if share:
            out.append({"family": p.parts[-5], "split": p.parts[-4], "adir": p.parts[-3], "share": share})
    return sorted(out, key=lambda r: -r["share"])


# ------------------------------------------------------------------ per-item passes, g norms (leaderboard, means page)


def item_passes(family: str, split: str, adir: str, _mtime: float, forms: bool = False) -> dict[str, bool] | None:
    """Item -> pass for one arm under the pipeline's own free scorer (jlm.score strict; jlm.mtproxy on the
    multi-token families), in the arm's vocabulary view; ``forms``: strict + forms (jlm.forms) on the single-token
    families. None when it cannot be rebuilt here (no tokenizer for the piece proxy)."""
    return _item_passes(family, split, view(family, split, adir), _mtime, forms and family not in MT_FAMILIES)


@st.cache_data(show_spinner="Scoring items…", max_entries=256)
def _item_passes(family: str, split: str, adir: str, _mtime: float, forms: bool = False) -> dict[str, bool] | None:
    from jlm import banks as jbanks
    from jlm import forms as jforms
    from jlm import mtproxy
    from jlm import score as jscore

    p = EVAL / family / split / adir / "readouts.jsonl"

    def compute():
        rows = _jsonl(p)
        if family in MT_FAMILIES:
            units = bank(family, split)["units"]
            return mtproxy.item_passes(rows, units) if units else None
        return jscore.strict_items(rows, jbanks.load(family, split), jforms.table(family) if forms else None)

    # kept per bank (bank.item_passes.json): rescoring every arm took ~11 s on the Leaderboard
    if forms:
        return _sidecar(p, "bank.item_passes_forms.json", [_size(p), _size(DEV / family / f"{split}.json"),
                                                           _size(jforms.path_of(family))], compute)
    return _sidecar(p, "bank.item_passes.json", [_size(p), _size(DEV / family / f"{split}.json")], compute)


@st.cache_data(show_spinner=False, max_entries=256)
def paired(a: dict[str, bool], b: dict[str, bool], ids: tuple[str, ...]) -> dict:
    """rate(a) - rate(b), paired item bootstrap 95 % interval (jlm.score.paired)."""
    from jlm import score as jscore

    return jscore.paired(a, b, list(ids))


def g_over_h(family: str, split: str, adir: str, _mtime: float) -> dict[int, float]:
    """Layer -> mean ||g|| / ||h|| over read cells, from the rank sidecar (ranks.jsonl h_norm, g_norm); {} on older arms."""
    return _g_over_h(family, split, view(family, split, adir), _mtime)


@st.cache_data(show_spinner=False, max_entries=128)
def _g_over_h(family: str, split: str, adir: str, _mtime: float) -> dict[int, float]:
    acc: dict[int, list[float]] = defaultdict(list)
    for r in _jsonl(EVAL / family / split / adir / "ranks.jsonl"):
        if r.get("g_norm") is not None and r.get("h_norm"):
            acc[r["layer"]].append(r["g_norm"] / r["h_norm"])
    return {L: sum(v) / len(v) for L, v in sorted(acc.items())}


@st.cache_data(show_spinner="Rebuilding g from the captures…", max_entries=32)
def mean_g(family: str, split: str, centre: str, ref: str, _mtime: float) -> dict:
    """Arm centre@ref's mean g over the read cells, per layer, rebuilt from the captures exactly as geometry() and
    centres_at() build it (jlm.geometry): {layers, mean [L, d]}. Raises FileNotFoundError without the captures."""
    import numpy as np


    hfsync.need_captures(family, split, centre, ref)  # the centre's own reference files
    f = _jfit(family, split, centre, ref)
    return {"layers": f.layers, "mean": np.stack([f.layer(L)[2].double().mean(0).float().numpy() for L in f.layers])}


# ------------------------------------------------------------------ analysis battery (experiments/analyse.py) and studies


@st.cache_data(show_spinner=False)
def study_cards(_stamp: float) -> dict[str, dict]:
    """Study id -> its card (notes/iteration-anthony/studies/<id>.card.yaml, schema in CARDS.md); a card that does not
    parse is skipped with its error under "_error"."""
    import yaml

    out = {}
    for p in sorted(STUDIES.glob("*.card.yaml")):
        sid = p.name[: -len(".card.yaml")]
        try:
            out[sid] = yaml.safe_load(p.read_text()) or {}
        except yaml.YAMLError as e:
            out[sid] = {"_error": str(e)}
    return out


def study_note(sid: str, card: dict | None = None) -> str | None:
    """The study's notes: <id>.md, or the file the card's ``notes`` key names (a study written up inside another's)."""
    for name in ([card["notes"]] if card and card.get("notes") else []) + [f"{sid}.md"]:
        if (p := STUDIES / name).exists():
            return p.read_text()
    return None


def studies() -> list[str]:
    """Studies with battery output under out/analysis/, newest first."""
    ds = [p for p in ANALYSIS.glob("*") if p.is_dir() and (any(p.glob("*.json")) or (p / "summary.md").exists())]
    return [p.name for p in sorted(ds, key=lambda p: -max((_mt(q) for q in p.iterdir()), default=0.0))]


@st.cache_data(show_spinner=False, max_entries=32)
def analysis(study: str, _stamp: float) -> dict:
    """{banks: {"family/split": per-bank JSON}, summary: summary.md text, note: notes/iteration-anthony/studies/<id>.md (or <id before "-">.md) text or None}."""
    d = ANALYSIS / study
    out = {}
    for p in sorted(d.glob("*.json")):
        try:
            r = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict) or "arms" not in r:  # a study's extra outputs (u4_overlap.json, diag-wiki.json)
            continue
        out[r.get("bank") or p.stem.replace("-", "/", 1)] = r
    note = STUDIES / f"{study}.md"
    if not note.exists():  # S4-val, U4-fit: a run of study S4 / U4
        note = STUDIES / f"{study.split('-')[0]}.md"
    return {"banks": out, "summary": (d / "summary.md").read_text() if (d / "summary.md").exists() else "",
            "note": note.read_text() if note.exists() else None}


@st.cache_data(show_spinner=False, max_entries=32)
def g_decoded(family: str, split: str, _stamp: float) -> dict[str, dict[int, list[str]]]:
    """arm -> layer -> top tokens of L(mean g), from any study's battery output for this bank (newest study wins)."""
    out: dict[str, dict[int, list[str]]] = {}
    for study in reversed(studies()):
        p = ANALYSIS / study / f"{family}-{split}.json"
        if p.exists():
            for a, per in (json.loads(p.read_text()).get("g_decoded") or {}).items():
                out[a] = {int(L): toks for L, toks in per.items()}
    return out


@st.cache_data(show_spinner="Loading the principal-component analysis…", max_entries=4)
def pc_explainer(_stamp: float) -> dict:
    """S7's principal-component data for views/pca.py: {"explainer": experiments/s7_pc_explainer.py output (per family:
    PC spectra, val cells on the top PCs, decoded PCs, removed / kept readouts), "targets": experiments/s7_pcs.py
    output (median target rank in the removed and kept parts)}; a key is None when its file is missing."""
    extra = ANALYSIS / "S7" / "extra"
    out = {}
    for key, name in (("explainer", "explainer.json"), ("targets", "pcs.json")):
        p = _get(extra / name)
        out[key] = json.loads(p.read_text()) if p.exists() else None
    return out
