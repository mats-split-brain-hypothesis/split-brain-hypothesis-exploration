"""Find customer records that are probably the same person typed differently."""
from typing import List, Tuple

from .distance import within_distance
from .normalize import normalize_name


def find_duplicates(names: List[str], max_distance: int = 2) -> List[Tuple[str, str]]:
    """All pairs of names whose normalised forms are within max_distance edits of each other.

    Each pair is (a, b) with a < b, using the original spellings; the list is sorted.
    """
    normalized = [(normalize_name(n), n) for n in names]
    pairs = set()
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            (na, a), (nb, b) = normalized[i], normalized[j]
            if within_distance(na, nb, max_distance):
                pairs.add((a, b) if a < b else (b, a))
    return sorted(pairs)
