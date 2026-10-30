"""Exact tests and intervals in pure Python (no scipy in the project venv)."""
from math import comb, sqrt


def wilson(k, n, z=1.959964):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def _hyper(a, r1, c1, N):
    # P(top-left cell = a) with row-1 total r1, col-1 total c1, grand total N
    return comb(c1, a) * comb(N - c1, r1 - a) / comb(N, r1)


def fisher(k1, n1, k2, n2):
    """Returns (two-sided, one-sided greater: arm1 > arm2, one-sided less)."""
    N = n1 + n2
    c1 = k1 + k2
    lo, hi = max(0, c1 - n2), min(n1, c1)
    probs = {a: _hyper(a, n1, c1, N) for a in range(lo, hi + 1)}
    p0 = probs[k1]
    two = sum(p for p in probs.values() if p <= p0 * (1 + 1e-7))
    greater = sum(p for a, p in probs.items() if a >= k1)
    less = sum(p for a, p in probs.items() if a <= k1)
    return min(two, 1.0), min(greater, 1.0), min(less, 1.0)


def binom_tail(k, n, p=0.5):
    """P(X >= k) for X ~ Bin(n, p)."""
    return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def sign_test(pos, neg):
    """Exact sign test on non-tied pairs: (two-sided, one-sided pos > neg)."""
    n = pos + neg
    one = binom_tail(pos, n)
    two = min(1.0, 2 * min(binom_tail(pos, n), binom_tail(neg, n)))
    return two, one


def mcnemar_exact(b, c):
    """Exact McNemar on discordant counts b, c: two-sided."""
    return sign_test(b, c)[0]
