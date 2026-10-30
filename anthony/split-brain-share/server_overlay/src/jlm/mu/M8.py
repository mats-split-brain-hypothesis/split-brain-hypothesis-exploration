"""M8 (round 4, night-3): a data-free S14bL, every bench-cell part replaced by the circuit's data-free parts.

S14bL = ``sched:40:kmx64+s14:template:64:mean=knnxd8l:a=0.5``. Its forms here, with no bank cell anywhere:
``sched:40:<early>+s14:<set>:64:mean=<late>:a=<alpha>`` with ``early`` and ``late`` from the aliases below (S14's
``mean=`` and the schedule's parts take names without ':' or '+').

- ``gn``: the data-free constant, ``m1:glosnone:inf`` (pool mean of the generic final-token texts; chat renders their own).
- ``gnw<lam>``: M1's whitening around it, e.g. ``gnw1`` = ``m1:glosnone:1``.
- ``gnp``: M2's projective form ``m2:glosnone`` (alpha per cell, cos metric); ``gnpc``: clipped to [0, 1];
  ``gnpr``: rms metric.
"""

from jlm import centres
from jlm.centres import CENTRES

CENTRES.update({
    "gn": lambda: _named("m1:glosnone:inf", "gn"),
    "gnp": lambda: _named("m2:glosnone", "gnp"),
    "gnpc": lambda: _named("m2:glosnone:clip", "gnpc"),
    "gnpr": lambda: _named("m2:glosnone:rms", "gnpr"),
})
for _lam in ("0.1", "0.3", "1", "3"):
    CENTRES[f"gnw{_lam}"] = lambda lam=_lam: _named(f"m1:glosnone:{lam}", f"gnw{lam}")


def _named(spec: str, name: str):
    c = centres.make(spec)
    c.name = name
    return c

# M12 (round 4): the fully data-free schedule (gnread list read off the generic cells), as one name for other parts
# (e.g. B's frame projection on top of it, ``m4p:0.02:frame:on=m12``).
CENTRES["m12"] = lambda: _named("sched:40:gnw1+s14:gnread:128:mean=gn:a=0.25", "m12")
