"""The seeded kmx centres are registered and differ from kmx64 only in the seed."""

from jlm import centres


def test_seeded_kmx_registered():
    c = centres.make("kmx64s1")
    assert c.name == "kmx64s1" and c.seed == 1 and c.k == 64 and c.pool_kind == "bench"
    assert centres.make("sched:40:kmx64s2+s14t64").name == "sched:40:kmx64s2+s14t64"
