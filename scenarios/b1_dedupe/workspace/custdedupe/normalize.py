"""Name normalisation applied before matching."""
import unicodedata


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and collapse whitespace, so 'José  Núñez' and 'jose nunez' compare equal."""
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())
