"""Edit distance between customer names."""


def levenshtein(a: str, b: str) -> int:
    """Number of single-character insertions, deletions or substitutions needed to turn a into b."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def within_distance(a: str, b: str, max_distance: int) -> bool:
    """True if levenshtein(a, b) <= max_distance."""
    if abs(len(a) - len(b)) > max_distance:
        return False
    return levenshtein(a, b) <= max_distance
