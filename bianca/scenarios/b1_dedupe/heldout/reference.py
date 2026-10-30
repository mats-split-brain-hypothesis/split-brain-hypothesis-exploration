"""Reference data generator and fast reference implementation for B1. Never shown to the model."""
import random
import unicodedata

FIRST = ["Anna", "Maria", "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas",
         "Sarah", "Karen", "Nancy", "Lisa", "Sandra", "Ashley", "Emily", "Olivia", "Noah", "Liam", "Sophia", "Lucas",
         "Mateo", "Amelia", "Elena", "Ivan", "Yuki", "Chen", "Fatima", "Omar", "Priya", "Raj", "José", "Zoë", "Chloé",
         "Björn", "Søren", "Ana", "Inés", "Agnieszka", "Katarzyna", "Mehmet", "Aylin", "Kwame", "Amara", "Hiroshi"]
SYL = ["ka", "to", "ri", "mo", "ne", "sa", "lu", "vi", "der", "son", "berg", "ov", "ski", "ez", "an", "el", "ma",
       "ra", "ti", "go", "ha", "shi", "wa", "ber", "lin", "ton", "ford", "ley", "ro", "na", "da", "cu", "pe", "zo"]
ALPHA = "abcdefghijklmnopqrstuvwxyz"


def normalize_name(name):
    decomposed = unicodedata.normalize("NFKD", name)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).lower().split())


def _surname(rng):
    return "".join(rng.choice(SYL) for _ in range(rng.randint(3, 4))).capitalize()


def _typo(s, rng):
    i = rng.randrange(len(s))
    op = rng.choice("sdit")
    c = rng.choice(ALPHA)
    if op == "s":
        return s[:i] + c + s[i + 1:]
    if op == "d":
        return s[:i] + s[i + 1:]
    if op == "t" and i < len(s) - 1:
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    return s[:i] + c + s[i:]


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def make_names(n, seed):
    rng = random.Random(seed)
    names, seen = [], set()
    while len(names) < n:
        base = f"{rng.choice(FIRST)} {_surname(rng)}"
        variants = [base]
        r = rng.random()
        if r < 0.05:
            variants.append(_typo(base, rng))
        elif r < 0.07:
            variants.append(_typo(_typo(base, rng), rng))
        elif r < 0.08:
            variants.append(_strip_accents(base).lower())
        for v in variants:
            if v not in seen and len(names) < n:
                seen.add(v)
                names.append(v)
    rng.shuffle(names)
    return names


def _within(a, b, k):
    if abs(len(a) - len(b)) > k:
        return False
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [k + 1] * len(b)
        lo, hi = max(1, i - k), min(len(b), i + k)
        best = cur[0] if lo == 1 else k + 1
        for j in range(lo, hi + 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] != b[j - 1]))
            cur[j] = v
            best = min(best, v)
        if best > k:
            return False
        prev = cur
    return prev[len(b)] <= k


def _deletes(s, k):
    res, frontier = {s}, {s}
    for _ in range(k):
        frontier = {w[:i] + w[i + 1:] for w in frontier for i in range(len(w))}
        res |= frontier
    return res


def reference_duplicates(names, max_distance=2):
    norm = {n: normalize_name(n) for n in names}
    index = {}
    for n in names:
        for d in _deletes(norm[n], max_distance):
            index.setdefault(d, []).append(n)
    pairs = set()
    for bucket in index.values():
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a, b = bucket[i], bucket[j]
                p = (a, b) if a < b else (b, a)
                if p not in pairs and _within(norm[a], norm[b], max_distance):
                    pairs.add(p)
    return sorted(pairs)
