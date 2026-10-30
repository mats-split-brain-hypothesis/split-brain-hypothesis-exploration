"""Overnight runs of the mu loop: which studies a night ran, which arms in out/eval belong to them, and the scores the
Overnight pages draw (macro change against a reference with a within-family bootstrap, and fresh splits pooled).

A night's studies are the cards whose ``owner`` names it (``owner: A (j-lens-mean-2e), night-2``), plus ``EXTRA``
(studies written up inside another's notes). An arm belongs to a study when

- the study's card lists it (``arms`` / ``controls``), or
- its centre, or any part of it, is registered by the study's ``jlm.mu`` module. Parts are read off the name: a
  schedule's two halves (``sched:<L>:<A>+<B>``), a ``mean=<centre>``, an ``s20xon:<a>:<base>``'s base, a matched null's
  inner centre (``famr:<seed>:<centre>``). A schedule whose parts are all older centres is S17's (depth schedules).

Its primary study (its colour) is the latest of those, except that a schedule mixing S20x's correction with S14's
template step is S21's. Kinds: ``reference`` (zero, fam), ``control`` (shuf. / rand. / famr: arms, the card's controls,
and random-subspace heads), ``supervised`` (anything built on other families' fit targets: S20x's corrections, S20u),
else ``label-free``.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

import catalog
import sources


@dataclass(frozen=True)
class Night:
    id: str  # as the cards' owner line names it
    title: str
    dates: str
    digest: str  # notes/iteration-anthony/overnight/<file>
    fresh: tuple[str, ...]  # held-out splits authored that night (pooled on the pages)
    extra: tuple[tuple[str, str, str, str], ...] = ()  # (id, title, instance, notes file) for studies with no card


NIGHTS = {
    "night-2": Night("night-2", "Night 2", "11–12 Oct 2026", "night-2-digest.md", ("val2", "val3"),
                     extra=(("S25", "Label-free answer-position directions", "B", "S20x.md"),)),
}

@dataclass(frozen=True)
class Candidate:
    short: str  # the name the night's notes use
    centre: str  # the arm's centre in out/eval (any ref, any readout)
    colour: str
    supervised: bool = False
    what: str = ""  # the mechanism, one or two sentences (HTML); every arm reads J_l (h - g)
    needs: str = ""  # what g is built from
    lens: str = "jlens"  # the map the arm reads through (catalog.LENSES)
    origin: str = ""  # for an older reference: where it comes from

    def matches(self, a: catalog.Arm) -> bool:
        return a.lens == self.lens and a.centre == self.centre


CLUSTER = "the mean of h's k-means cluster (64 clusters over every family's fit read cells, no labels)"
#: Each night's best candidates: the rows of its finalists table (studies/finalists-night2.md), plus the references.
CANDIDATES = {
    "night-2": (
        Candidate("zero", "zero", "#8a96a5", what="No centring: reads J<sub>l</sub> h, the released lens.",
                  needs="nothing"),
        Candidate("fam", "fam", "#5f6b7a", what="g = the mean read state of the item's family at that layer, the "
                  "item's own group left out.", needs="the family label"),
        Candidate("s14t64", "s14t64", "#d62728", what="g = P<sub>B</sub> h: removes h's component along the lens's "
                  "reading directions of 64 template tokens (chat special tokens and frequent chat tokens, never a "
                  "target), so nothing the lens would read as the template survives.", needs="a token list; no reference cells"),
        Candidate("S14k", "sched:40:kmx64+s14t64", "#ff7f0e", what=f"Depth schedule. Up to L40: g = {CLUSTER}. "
                  "Above L40: s14t64's template removal.", needs="unlabelled fit cells"),
        Candidate("S14b", "sched:40:kmx64+s14:template:64:mean=kmx64:a=0.5", "#bcbd22", what="As S14k up to L40. "
                  "Above it, half the cluster mean comes off first, then the template directions: reads "
                  "J (I − P<sub>B</sub>)(h − ½ μ<sub>cluster</sub>).", needs="unlabelled fit cells"),
        Candidate("S14b-x", "sched:40:kmx64+s14:template:64:mean=knnxs8:a=0.5", "#2ca02c", what="As S14b, but the "
                  "late half-mean is the mean of h's 8 nearest fit cells (cosine, any family), excluding cells that "
                  "share the item's carrier sentence.", needs="unlabelled fit cells"),
        Candidate("S14bL", "sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5", "#00a6a6", what="As S14b-x, and the "
                  "late neighbours also exclude cells in the item's own non-English prompt language (detected from the "
                  "prompt text), so the language itself is not centred away (keeps multilingual_mt's language unit).",
                  needs="unlabelled fit cells; language detected from text"),
        Candidate("knnxs8", "knnxs8", "#1f77b4", what="At every layer, g = the mean of the 8 nearest fit read cells "
                  "(cosine, any family), none sharing the cell's carrier sentence (knnx8 without its same-sentence "
                  "leak).", needs="unlabelled fit cells"),
        Candidate("S20x", "s20xt:1", "#e377c2", True, what="g = family mean + the average of the other families' "
                  "learned corrections. Each correction is that family's best constant g, fitted with its fit targets, "
                  "minus its family mean (S20's ceiling); the read family and its _mt twin are left out. Mostly shifts "
                  "word form (punctuation down, names up, English over CJK).",
                  needs="family label + <b>other families' fit targets</b>"),
        Candidate("S21", "sched:40:s20xon:1:kmx64+s14t64", "#9467bd", True, what="S14k with S20x's averaged "
                  "correction added to the cluster mean up to L40; template removal above.",
                  needs="unlabelled fit cells + <b>other families' fit targets</b>"),
        Candidate("S21b", "sched:40:s20xon:1:kmx64+s14:template:64:mean=kmx64:a=0.5", "#8c564b", True, what="S14b "
                  "with S20x's averaged correction added to the cluster mean up to L40.",
                  needs="unlabelled fit cells + <b>other families' fit targets</b>"),
    ),
}
#: Older arms shown beside a night's candidates as references: the previous night's best candidates and the plain J++
#: lens. Not night arms: they are added to the night's pages as references wherever they were read.
PRIOR = {
    "night-2": (
        Candidate("knnx8 (pilot-1)", "knnx8", "#6b6b00", origin="pilot-1, S4", what="g = the mean of the 8 nearest fit "
                  "read cells (cosine, any family, own item out). Pilot-1's best label-free centre; its DM gain is a "
                  "same-sentence leak (fixed by knnxs8).", needs="unlabelled fit cells"),
        Candidate("pco16 (pilot-1)", "pco16", "#7a4fb8", origin="pilot-1, S7", what="g = μ<sub>fam</sub> + P(h − "
                  "μ<sub>fam</sub>), P the projection on the family's top 16 principal directions: the family mean plus "
                  "the family's own axes of variation removed.", needs="the family label + its fit cells"),
        Candidate("J++", "zero", "#c2417a", lens="jpp", origin="Ayonrinde & Lindsey 2026", what="No centring, read "
                  "through the J++ lens instead of the J-lens: a different linear map from h to the vocabulary.",
                  needs="nothing (the J++ map)"),
    ),
}
NULL_WHAT = ("Matched null: g = fam + a random direction (one per layer) with the norm of {x}'s change from fam; 3 seeds "
             "averaged. If {x} beat this, its gain is content, not norm.")
OVERNIGHT = sources.REPO_ROOT / "notes" / "iteration-anthony" / "overnight"
REFERENCES = {"zero", "fam"}
POOLED = "val2+val3"
#: Centre heads that are controls by construction: random subspaces / directions / clusters in place of the real one.
CONTROL_HEAD = re.compile(r"^(s14r|s14famr|s15r|s16pr|s18r|s19r16sh|s20xr|s20xron|kmxr|famr)\d*$")
#: Centre heads whose g holds other families' fit targets (S20x's corrections, S20u's learned constant).
SUPERVISED_HEAD = re.compile(r"^(s20x|s20xt|s20xon|s20xonrms|s20x1|s20xk|s20xkrms|s20xm|s20xp|s20xu|s20xtrms|s20u)$")
#: jlm.mu modules whose centres count under another study.
MODULE_STUDY = {"xcheck_e1": "S14"}  # B's k-means seed cross-check of S14k


def _order(sid: str) -> tuple:
    m = re.match(r"([A-Za-z]+)(\d+)(.*)", sid)
    return (m[1], int(m[2]), m[3]) if m else (sid, 0, "")


@lru_cache(maxsize=8)
def studies(night: str, _stamp: float) -> dict[str, dict]:
    """Study id -> {title, instance, status, verdict, card (or None), notes} for one night, in study order."""
    cards = sources.study_cards(_stamp)
    out = {}
    for sid, c in cards.items():
        if night in str(c.get("owner", "")):
            out[sid] = {"title": c.get("title", sid), "instance": str(c.get("owner", "?"))[:1], "status": c.get("status"),
                        "verdict": c.get("verdict", ""), "card": c, "notes": c.get("notes") or f"{sid}.md"}
    for sid, title, inst, notes in NIGHTS[night].extra:
        out.setdefault(sid, {"title": title, "instance": inst, "status": None, "verdict": "", "card": None, "notes": notes})
    return dict(sorted(out.items(), key=lambda kv: _order(kv[0])))


def _parts(centre: str) -> list[str]:
    """The centres a composite centre is built from (itself included), read off its name."""
    out = [centre]
    if centre.startswith("famr:"):  # matched null: famr:<seed>:<inner>
        out += _parts(centre.split(":", 2)[2])
    elif centre.startswith("sched:"):  # sched:<L>:<A>+<B>
        early, _, late = centre.split(":", 2)[2].partition("+")
        out += _parts(early) + _parts(late)
    else:
        out += [t for t in re.split(r"[:=]", centre)[1:] if re.match(r"[a-z]", t)]  # mean=knnxd8l, s20xon:1:kmx64
    return out


@lru_cache(maxsize=4096)
def _module_study(centre: str) -> str | None:
    mod = catalog._module(centre)
    if mod is None:
        return None
    short = mod.__name__.rpartition(".")[2]
    return MODULE_STUDY.get(short, short)


@dataclass(frozen=True)
class Member:
    study: str  # primary study (colour, grouping)
    studies: frozenset[str]  # every night study the arm belongs to
    kind: str  # reference | label-free | supervised | control


def _heads(centre: str) -> list[str]:
    return [p.split(":")[0] for p in _parts(centre)]


def member(arm: catalog.Arm, night: str, _stamp: float) -> Member | None:
    """The arm's place in the night, or None when it is not one of the night's arms (nor a reference: zero, fam, or
    one of the older arms in ``PRIOR``)."""
    ss = studies(night, _stamp)
    if not arm.control and any(c.matches(arm) for c in PRIOR.get(night, ())):
        return Member("reference", frozenset(), "reference")  # an older arm shown as a reference
    if arm.lens != "jlens":
        return None
    if arm.centre in REFERENCES:
        return Member("reference", frozenset(), "reference")
    listed = {sid for sid, s in ss.items() if s["card"] and arm.name in (s["card"].get("arms") or []) + (s["card"].get("controls") or [])}
    in_controls = any(arm.name in (ss[sid]["card"].get("controls") or []) for sid in listed)
    parts = _parts(arm.inner)
    found = {s for p in parts if (s := _module_study(p)) in ss}
    if arm.inner.startswith("famr:"):
        found.add("S24")  # C's post-read matched nulls
    if arm.inner.startswith("sched:") and not found and "S17" in ss:
        found.add("S17")  # a depth schedule of older centres
    if not found and not listed:
        return None
    allx = found | listed  # listed alone: an older centre a night card compares against (knnx8 in S16)
    if {"S20x", "S14"} <= found and arm.inner.startswith("sched:") and "S21" in ss:
        primary = "S21"
    else:
        primary = max(found or allx, key=_order)
    heads = _heads(arm.inner)
    if arm.control or in_controls or any(CONTROL_HEAD.match(h) for h in heads) or ":rand" in arm.inner:
        kind = "control"
    elif any(SUPERVISED_HEAD.match(h) for h in heads):
        kind = "supervised"
    else:
        kind = "label-free"
    return Member(primary, frozenset(allx | {primary}), kind)


# ------------------------------------------------------------------ scores

def splits(night: str) -> list[str]:
    """The splits a night's scores page offers, in reading order."""
    fresh = list(NIGHTS[night].fresh)
    return ["fit", "val", *fresh, POOLED, *[s for s in sources.FRESH if s not in fresh], "bench"]


def _ids(r: dict, forms: bool) -> list[str]:
    return list(r["forms_ids"] if forms and r.get("forms_ids") else r["scored_ids"])


def passes(R: dict, family: str, split: str, arm: str, forms: bool) -> dict[str, float] | None:
    """Item -> pass (0 / 1) for one arm on one bank, from the cached per-item scorer. ``famr:*:<inner>`` with seed ``*``
    averages the three matched-null seeds (as experiments/s24_pool.py does)."""
    forms = forms and family not in sources.MT_FAMILIES
    if split == POOLED:
        out = {}
        for s in NIGHTS["night-2"].fresh:
            p = passes(R, family, s, arm, forms)
            if p is None:
                return None
            out.update({f"{s}/{k}": v for k, v in p.items()})
        return out
    r = R.get(family, {}).get(split)
    if r is None:
        return None
    if arm.startswith("famr:*:"):
        seeds = [a for a in r["arms"] if a.startswith("famr:") and a.split(":", 2)[2] == arm.split(":", 2)[2]]
        ps = [passes(R, family, split, a, forms) for a in seeds]
        if not ps or None in ps:
            return None
        return {k: float(np.mean([p[k] for p in ps])) for k in ps[0]}
    if arm not in r["arms"]:
        return None
    adir = sources.arm_dir(arm)
    p = sources.item_passes(family, split, adir, sources.readouts_mtime(family, split, adir), forms)
    if p is None:
        return None
    ids = set(_ids(r, forms))
    return {k: float(v) for k, v in p.items() if k in ids}


def arms_on(R: dict, split: str, families: list[str]) -> set[str]:
    """Arm names scored on ``split`` for any of ``families`` (the pooled split: arms on every fresh split of a family)."""
    if split == POOLED:
        out = set()
        for f in families:
            per = [set(R.get(f, {}).get(s, {}).get("arms", {})) for s in NIGHTS["night-2"].fresh]
            out |= set.intersection(*per) if all(per) else set()
        return out
    return {a for f in families for a in R.get(f, {}).get(split, {}).get("arms", {})}


def families_on(R: dict, split: str) -> list[str]:
    if split == POOLED:
        return [f for f in sources.ALL_FAMILIES if all(s in R.get(f, {}) for s in NIGHTS["night-2"].fresh)]
    return [f for f in sources.ALL_FAMILIES if split in R.get(f, {})]


def macro_change(P: dict, ref: dict, families: list[str], n_boot: int = 2000, seed: int = 0) -> dict | None:
    """Macro over ``families`` of each family's paired change (arm - ref) on the items both cover, and its 95 % interval
    from a bootstrap that resamples items within each family (the same draws for every arm, so arms compare paired).
    ``P`` / ``ref``: family -> item -> pass. Returns {d, ci, per: {family: d}, n} or None without a common family."""
    per, boots = {}, []
    for f in families:
        a, b = P.get(f), ref.get(f)
        if not a or not b:
            continue
        ids = sorted(set(a) & set(b))
        if not ids:
            continue
        d = np.array([a[i] - b[i] for i in ids])
        per[f] = float(d.mean())
        idx = _draws(f, len(ids), n_boot, seed)
        boots.append(d[idx].mean(axis=1))
    if not per:
        return None
    bm = np.mean(boots, axis=0)
    return {"d": float(np.mean(list(per.values()))), "ci": [float(np.quantile(bm, 0.025)), float(np.quantile(bm, 0.975))],
            "per": per, "n": len(per)}


@lru_cache(maxsize=256)
def _draws(family: str, n: int, n_boot: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng([seed, n, *family.encode()])
    return rng.integers(0, n, size=(n_boot, n))


def rate_ci(p: dict, n_boot: int = 2000) -> tuple[float, float, float] | None:
    """A pass rate over items and its item-bootstrap 95 % interval."""
    if not p:
        return None
    x = np.array(list(p.values()), dtype=float)
    bm = x[_draws("rate", len(x), n_boot, 2)].mean(axis=1)
    return float(x.mean()), float(np.quantile(bm, 0.025)), float(np.quantile(bm, 0.975))


def per_family_ci(a: dict, b: dict, n_boot: int = 2000) -> tuple[float, float, float] | None:
    """One family's paired change and its item-bootstrap 95 % interval."""
    ids = sorted(set(a) & set(b))
    if not ids:
        return None
    d = np.array([a[i] - b[i] for i in ids])
    bm = d[_draws("one", len(ids), n_boot, 1)].mean(axis=1)
    return float(d.mean()), float(np.quantile(bm, 0.025)), float(np.quantile(bm, 0.975))


def digest_sections(night: str) -> dict[str, str]:
    """The night's digest split at its ``## `` headings (title -> markdown), with links to study notes pointed at the
    dashboard's Studies page."""
    p = OVERNIGHT / NIGHTS[night].digest
    if not p.exists():
        return {}
    text = re.sub(r"\]\(\.\./studies/([A-Za-z0-9-]+)\.md\)", lambda m: f"](/study?study={m[1]})", p.read_text())
    out, cur = {}, "_head"
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = ""
        else:
            out[cur] = out.get(cur, "") + line + "\n"
    return out


RANK_EXCLUDED = ("user_modeling", "directed_modulation")  # pass can come from reading the prompt (S11, U1)


def candidate_ranking(night: str, _stamp: float) -> dict[str, float]:
    """Each of the night's candidates (not zero / fam) -> its macro change against fam on val, strict, cos, over every
    family but user_modeling / directed_modulation: the Night 2 scores page's default view. Best first."""
    return _ranking(night, _stamp)


@lru_cache(maxsize=8)
def _ranking(night: str, _stamp: float) -> dict[str, float]:
    R = sources.results(_stamp)
    fams = [f for f in families_on(R, "val") if f not in RANK_EXCLUDED]
    ref = {f: passes(R, f, "val", "fam@fit|cos", False) for f in fams}
    out = {}
    for c in CANDIDATES[night]:
        if c.centre in REFERENCES:
            continue
        P = {f: passes(R, f, "val", f"{c.centre}@fit|cos", False) for f in fams}
        if (ch := macro_change(P, ref, fams)) is not None:
            out[c.centre] = ch["d"]
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


class Picker:
    """The arm pickers' grouping with a night's candidates in a group of their own (Passage → readouts, Scores): drawn to
    the right of the best candidates (the controls move to their own folded row), ranked best first by
    ``candidate_ranking``, each pill showing its number. ``fold_others``: "Other centres" also folded."""

    def __init__(self, arms: list[catalog.Arm], held_ref: str, _stamp: float, night: str = "night-2",
                 fold_others: bool = False) -> None:
        self.by_name = {a.name: a for a in arms}
        self.held_ref, self.fold_others = held_ref, fold_others
        self.group_name = f"{NIGHTS[night].title} study centres"
        self.rank = candidate_ranking(night, _stamp)
        self.short = {c.centre: c.short for c in CANDIDATES[night]}
        self.help = (f" {self.group_name}: the night's finalists, best first; the number is each one's macro change "
                     "against fam on val (strict, cos, every family but user_modeling / directed_modulation; the "
                     f"{NIGHTS[night].title} scores page).")

    def pos(self, a: catalog.Arm) -> int | None:
        """The arm's place in the night's ranking (None: not one of its candidates)."""
        return list(self.rank).index(a.centre) if a.lens == "jlens" and not a.control and a.centre in self.rank else None

    def group(self, name: str) -> str:
        a = self.by_name[name]
        return self.group_name if self.pos(a) is not None else catalog.group(a)

    def label(self, name: str) -> str:
        a = self.by_name[name]
        if self.pos(a) is None:
            return a.label
        return (f"{self.short[a.centre]} {self.rank[a.centre]:+.3f}"
                + (f" · {catalog.REF_SHORT.get(a.ref, a.ref)}" if a.ref and a.ref != self.held_ref else ""))

    def order(self, a: catalog.Arm) -> tuple:
        """Baselines and older centres in catalog order, then the night's candidates best first."""
        p = self.pos(a)
        return (p is not None, p if p is not None else 0, a.sort_key)

    def beside(self, g: str) -> str | None:
        return self.group_name if g.endswith("best candidates") else catalog.beside(g)

    def fold(self, g: str) -> bool:
        return catalog.folded(g) or (self.fold_others and g == catalog.OTHERS)

    def names(self) -> list[str]:
        return [a.name for a in sorted(self.by_name.values(), key=self.order)]

    def pills(self, label: str, default: list[str], key: str, help: str = "") -> list[str]:
        """``ui.grouped_pills`` with this grouping; the picked names in display order."""
        import ui

        picked = ui.grouped_pills(label, self.names(), self.group, default, order=catalog.group_order, fold=self.fold,
                                  beside=self.beside, format_func=self.label, key=key, help=help + self.help)
        return sorted(picked or [], key=lambda n: self.order(self.by_name[n]))
