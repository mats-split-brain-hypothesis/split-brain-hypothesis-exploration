"""White-bear steering (Raman, Wierzbicki & Fournier, 2026): the reference implementation."""

from .direction import steering_vectors, white_bear_direction
from .pairs import load_pairs

__version__ = "0.1.0"
__all__ = ["load_pairs", "white_bear_direction", "steering_vectors"]
