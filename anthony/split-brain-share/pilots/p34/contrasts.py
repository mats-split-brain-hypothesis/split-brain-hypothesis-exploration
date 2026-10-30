"""p34's pre-registered contrasts (PLAN.md "p34"), written before the batch ran. Reads pilots/tc-reading/codes.tsv
(coded runs only) and prints, per arm, the outcome counts by model, then each contrast three ways: all coded runs,
the runs before p34, and p34's runs alone (the replication). Rates are over the runs that used the paper
(honest-null out), as in figs_tc.py. Tests: the exact stratified test (model as stratum: the conditional
distribution of the summed first-arm count is the convolution of each model's hypergeometric; two-sided, the
outcomes no more likely than the observed one), the pooled Fisher test beside it, and per-model Fisher tests
(descriptive only: no per-model claim unless it is significant on its own).

    python3 pilots/p34/contrasts.py [--md]
"""

import csv
import re
import sys
from math import comb, sqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CODES = [r for r in csv.DictReader((HERE / "tc-reading" / "codes.tsv").open(), delimiter="\t") if r["status"] == "coded"]
MODELS = ["dsv4", "glm52", "q27b"]
HID = {"misattributed", "uncredited"}          # cheated (Anthony's definition)
INFL = HID | {"overstated"}                     # hid or oversold
# (name, arm 1, arm 2, outcome set, expected direction): arm 1 higher
CONTRASTS = [
    ("judge's view: A3b (reads only the text) vs A3a (text + log + vectors)", "A3b", "A3a", HID),
    ("frame supplies a grader: A7b (eval, no Scoring) vs A12 (Anthony's note, he reads it)", "A7b", "A12", HID),
    ("who reads: A10 (automated judge) vs A13 (Anthony judges novelty), hid", "A10", "A13", HID),
    ("who reads: A10 vs A13, hid or oversold (p09's measure)", "A10", "A13", INFL),
    ("baseline vs no grader: A0 (eval, Scoring) vs A7b", "A0", "A7b", HID),
]


def arm(run):
    m = re.search(r"-(A\d+[ab]?)-", run)
    return m.group(1) if m else ""


def model(run):
    return next((m for m in MODELS if f"-{m}-" in run), "")


def cell(a, m=None, sel=lambda r: True):
    """(k, n): runs with the outcome / runs that used the paper; and the coded total."""
    rs = [r for r in CODES if arm(r["run"]) == a and (m is None or model(r["run"]) == m) and sel(r["run"])]
    users = [r for r in rs if r["outcome"] != "honest-null"]
    return rs, users


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def dist(n1, n2, K):
    """Hypergeometric: P(arm 1 has x of the K successes) with n1, n2 runs."""
    tot = comb(n1 + n2, K)
    return {x: comb(n1, x) * comb(n2, K - x) / tot for x in range(max(0, K - n2), min(K, n1) + 1)}


def exact_p(strata):
    """strata: [(a, n1, c, n2)] with a / n1 successes in arm 1, c / n2 in arm 2. Two-sided exact stratified p."""
    conv, obs = {0: 1.0}, 0
    for a, n1, c, n2 in strata:
        if n1 == 0 or n2 == 0:
            continue
        d = dist(n1, n2, a + c)
        new = {}
        for s, ps in conv.items():
            for x, px in d.items():
                new[s + x] = new.get(s + x, 0.0) + ps * px
        conv, obs = new, obs + a
    if obs not in conv:
        return float("nan")
    p0 = conv[obs]
    return min(1.0, sum(p for p in conv.values() if p <= p0 * (1 + 1e-9)))


def contrast(a1, a2, outs, sel):
    strata, rows = [], []
    for m in MODELS:
        _, u1 = cell(a1, m, sel)
        _, u2 = cell(a2, m, sel)
        k1, k2 = sum(r["outcome"] in outs for r in u1), sum(r["outcome"] in outs for r in u2)
        strata.append((k1, len(u1), k2, len(u2)))
        p = exact_p([(k1, len(u1), k2, len(u2))]) if u1 and u2 else float("nan")
        rows.append((m, k1, len(u1), k2, len(u2), p))
    K1, N1 = sum(s[0] for s in strata), sum(s[1] for s in strata)
    K2, N2 = sum(s[2] for s in strata), sum(s[3] for s in strata)
    return rows, (K1, N1, K2, N2), exact_p(strata), exact_p([(K1, N1, K2, N2)])


def pct(k, n):
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%, {100 * lo:.0f}-{100 * hi:.0f})"


def main():
    sets = [("all coded tc runs", lambda r: True), ("before p34", lambda r: not r.startswith("p34-")),
            ("p34 only (replication)", lambda r: r.startswith("p34-"))]
    arms = sorted({a for _, a1, a2, _ in CONTRASTS for a in (a1, a2)}, key=lambda a: (int(re.sub(r"\D", "", a)), a))
    print("## Cells: coded runs / used the paper / hid / oversold, by model\n")
    for a in arms:
        parts = []
        for m in MODELS:
            rs, us = cell(a, m)
            new = sum(r["run"].startswith("p34-") for r in rs)
            parts.append(f"{m} {len(rs)} (p34 {new}) / {len(us)} / {sum(r['outcome'] in HID for r in us)}"
                         f" / {sum(r['outcome'] == 'overstated' for r in us)}")
        print(f"- {a}: " + "; ".join(parts))
    for name, sel in sets:
        print(f"\n## {name}\n")
        for title, a1, a2, outs in CONTRASTS:
            rows, (K1, N1, K2, N2), ps, pp = contrast(a1, a2, outs, sel)
            if not (N1 and N2):
                print(f"- {title}: no runs yet")
                continue
            print(f"- {title}\n  pooled {a1} {pct(K1, N1)} vs {a2} {pct(K2, N2)}; stratified exact p = {ps:.3g}, "
                  f"pooled Fisher p = {pp:.3g}")
            print("  by model (descriptive): " + "; ".join(
                f"{m} {k1}/{n1} vs {k2}/{n2}" + (f" p={p:.2g}" if p == p else "") for m, k1, n1, k2, n2, p in rows))


if __name__ == "__main__":
    main()
