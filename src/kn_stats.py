"""Wilson interval and two-sided Fisher exact test, no scipy."""
from math import comb, sqrt


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def fisher(a, n1, b, n2):
    """Two-sided Fisher exact p for a/n1 vs b/n2 (sum of tables at most as likely as the observed one)."""
    K, N = a + b, n1 + n2
    def p(x):
        return comb(K, x) * comb(N - K, n1 - x) / comb(N, n1)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, K - n2), min(K, n1) + 1) if p(x) <= obs * (1 + 1e-9)))
