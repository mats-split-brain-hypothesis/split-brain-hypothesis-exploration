"""Recompute the unpaired two-arm p-values the overview map reports, from the k/n it reports.

Each claim: (row, what, k1, n1, k2, n2, claimed p as text, claimed sidedness or None).
Paired tests (McNemar, sign tests over prompts) and stratified tests can't be recomputed
from marginal k/n; they are listed separately with what would be needed.
"""
import sys
sys.path.insert(0, sys.path[0])
from audit_stats import fisher, wilson, sign_test

CLAIMS = [
    ("1b", "no-metric: padded, score vs vague", 2, 30, 4, 30, "0.69", None),
    ("1b", "no-metric: hidden target reached, score vs vague", 5, 30, 0, 30, "0.06", None),
    ("1b", "replication: hidden target, score vs vague", 10, 60, 0, 60, "0.002", None),
    ("1b", "replication: padded, score vs vague", 2, 60, 4, 60, "0.69", None),
    ("1g", "time-matched: automated framing vs none (no STOP)", 3, 6, 1, 6, "0.55", None),
    ("1g", "time-matched: no STOP vs STOP", 4, 12, 0, 6, "0.25", None),
    ("1g", "scale-up: framing vs none", 10, 20, 13, 20, "0.90", "one-sided greater"),
    ("1k", "redesign: special first, grader vs person", 24, 30, 21, 30, "0.55", None),
    ("1l", "follow-up 1: gamed episodes, person vs grader", 15, 15, 11, 15, "0.125", None),
    ("1l", "follow-up 3: grader overt gaming, no disclaimer vs disclaimer (1/15)", 10, 15, 1, 15, "0.004", None),
    ("1l", "follow-up 3: grader overt gaming, no disclaimer vs disclaimer (2/15)", 10, 15, 2, 15, "0.004", None),
    ("1s", "grading on vs off, hack at first submission", 12, 18, 0, 18, "4e-5 (stratified)", None),
    ("2m", "test of me: failure reported vs recorded", 6, 15, 0, 10, "0.02-0.06", None),
    ("2n", "probe real: plain vs graded sentence", 24, 30, 2, 30, "8e-9", None),
    ("2o", "honest commit: person vs no reader", 12, 15, 4, 15, "0.009", None),
    ("2o", "honest commit: AI reviewer vs no reader", 11, 15, 4, 15, "0.027", None),
    ("2o", "honest commit: person vs log control", 12, 15, 5, 15, "0.025", None),
    ("2o", "full episodes: hacks, no reader vs person", 3, 4, 1, 5, "0.21", None),
    ("2p", "D1 scale-up: stand-in graded vs real, all 20", 8, 20, 1, 20, "0.0098", "one-sided greater"),
    ("2p", "D1 new 10: stand-in graded vs real", 5, 10, 1, 10, "0.07", "one-sided greater"),
    ("2p", "D1 hand-rule hacks", 6, 20, 1, 20, "0.046", "one-sided greater"),
    ("2p", "D1 test of me at most one failure", 4, 20, 1, 20, "0.17", None),
    ("2p", "D1 probe: >=1 real answer, real vs graded transcripts", 14, 20, 3, 20, "0.0005", "one-sided greater"),
    ("2p", "G1: stand-in graded vs real", 1, 10, 5, 10, "0.14", "two-sided"),
    ("2p", "G1+D1 pooled: stand-in graded vs real", 9, 30, 6, 30, "0.28", None),
    ("2p", "G3: stand-in after switch, stays-on vs off", 3, 10, 0, 9, "0.12", "one-sided greater"),
    ("2p", "G3: raises making test pass after switch, on vs off", 10, 10, 1, 9, None, None),
    ("2q", "exp3: honest, person reads code vs none", 12, 15, 4, 15, "0.009", "two-sided"),
    ("2q", "exp3: honest, detector vs none", 11, 15, 4, 15, "0.027", None),
    ("2q", "exp3: honest, detector (if borderline wrong) vs none", 10, 15, 4, 15, "0.066", None),
    ("2q", "exp3: honest, reply-only reader vs none", 9, 15, 4, 15, "0.14", None),
    ("2q", "exp3: hack plans, none vs detector", 3, 15, 0, 15, "0.22", None),
    ("2q", "exp5 (lcbhard_99): honest, person vs none", 4, 15, 1, 15, "0.33", None),
    ("2q", "exp5: honest, detector vs none", 3, 15, 1, 15, "0.60", None),
    ("2q", "exp6 (lcbhard_58): honest, detector vs none", 7, 15, 3, 15, "0.25", None),
    ("2q", "exp7: hack plans, none vs detector (3 tasks)", 8, 42, 0, 44, "0.002", None),
    ("2q", "exp4: full episodes passed, none vs person", 3, 4, 1, 4, "0.49", None),
    ("2q", "exp4: full episodes passed, none vs detector", 3, 4, 0, 4, "0.14", None),
    ("2q", "pooled full episodes: none vs person", 6, 8, 2, 9, "0.057", None),
    ("2q", "exp8: full episodes passed, none vs detector", 4, 8, 0, 8, "0.077", None),
    ("2q", "exp8 without lcbhard_101", 4, 6, 0, 6, "0.061", None),
    ("2q", "exp8+exp4 pooled", 7, 12, 0, 12, "0.005", None),
    ("2r", "G1 chat: verification claims graded vs real", 6, 30, 7, 30, "1.0", None),
    ("2r", "G1 chat: grader talk graded vs real", 14, 30, 4, 30, "0.01", None),
    ("2r", "harder chat: grader talk graded vs real", 28, 30, 19, 30, "0.010", None),
    ("3g", "E1: false full-pass claim, automated (3/10) vs colleague", 3, 10, 0, 10, "0.21", None),
    ("3h", "Dark Mode R: last browser search, graded vs not", 8, 15, 0, 15, "0.002", None),
    ("3i", "padded: person vs plain", 37, 40, 39, 40, "diff -5 pts, CI -10 to 0", None),
    ("1o", "score planning, off vs neutral", 8, 47, 38, 51, None, None),
]


def fmt(p):
    return f"{p:.2g}" if p < 0.001 else f"{p:.3f}"


print(f"{'row':4} {'comparison':66} {'k1/n1':>7} {'k2/n2':>7}  {'claimed':>18}  {'2-sided':>8} {'1-sided':>8}")
for row, what, k1, n1, k2, n2, claimed, side in CLAIMS:
    two, greater, less = fisher(k1, n1, k2, n2)
    one = greater if k1 / n1 >= k2 / n2 else less
    print(f"{row:4} {what[:66]:66} {k1:>3}/{n1:<3} {k2:>3}/{n2:<3}  {str(claimed):>18}  {fmt(two):>8} {fmt(one):>8}  {side or ''}")

print()
print("Wilson checks")
for k, n, claim in [(0, 18, "0-0.18"), (12, 18, "0.44-0.84"), (0, 10, "0-0.28"), (10, 20, ""), (13, 20, "")]:
    lo, hi = wilson(k, n)
    print(f"  {k}/{n}: {lo:.3f}-{hi:.3f}  claimed {claim}")

print()
print("Sign tests")
print("  1a: 4 of 4 non-tied pairs (6 prompts, 2 ties):", sign_test(4, 0))
print("  2e: 8 higher, 0 lower (10 tasks):", sign_test(8, 0))
