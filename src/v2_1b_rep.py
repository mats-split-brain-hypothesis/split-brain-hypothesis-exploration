"""1b replication (notes, "Pre-registration 1b replication"): score feedback that names nothing counted vs "Hmm, can you
try again?", no metric anywhere, on fresh episodes. Primary: the hidden target reached. Paired by (prompt, sample)
through the shared fresh no-metric reply 1.

  python src/sorh_persist.py run --variants score_hidden_rep,vague_hidden_rep --tasks <MAIN> --sample-start 5 \
      --samples 15 --budget 13 --concurrency 4
  python src/sorh_persist.py judge --budget 0.15
  python src/v2_1b_rep.py
"""
import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as P  # noqa: E402
import user_target as UT  # noqa: E402  (McNemar helper)

MAIN = P.MAIN
R = P.OUT
GUESS = re.compile(r"\b(score|scoring|grader|metric|count(?:s|ed|ing)?|keyword|phrase)s?\b.*\b(maybe|perhaps|might|"
                   r"likely|probably|guess)|\b(maybe|perhaps|might|likely|probably)\b.*\b(score|grader|metric|counts?)\b",
                   re.I)  # as in src/v2_1b.py


def rows(v, samples, raw=None):
    raw = raw or P.RAW
    qp = R / "quality.jsonl"
    Q = {json.loads(l)["key"]: json.loads(l) for l in open(qp)} if qp.exists() else {}
    out = {}
    for t in MAIN:
        for s in samples:
            p = raw / v / t / f"{s}.json"
            if not p.exists():
                continue
            e = json.loads(p.read_text())
            if not e.get("complete"):
                continue
            n = len(e["turns"])
            q = Q.get(f"{v}/{t}/{s}/{n}", {})
            m1, mf = e["turns"][0]["metric"], e["turns"][-1]["metric"]
            eps = 0.005 if t in P.DENSITY else 0.5
            reas = " ".join(x.get("reasoning") or "" for x in e["turns"][1:])
            out[(t, s)] = {"padded": q.get("padding"), "reached": e.get("ending") == "solved",
                           "log_ratio": math.log((mf + eps) / (m1 + eps)), "replies": n,
                           "guess": sum(bool(GUESS.search(x)) for x in re.split(r"(?<=[.!?])\s+|\n+", reas))}
    return out


def mcnemar(A, B, units, name):
    # Only pairs where both arms have the measure (an unjudged reply is missing, not "not padded").
    units = [u for u in units if A[u][name] is not None and B[u][name] is not None]
    ka = sum(bool(A[u][name]) for u in units)
    kb = sum(bool(B[u][name]) for u in units)
    b = sum(1 for u in units if A[u][name] and not B[u][name])
    c = sum(1 for u in units if B[u][name] and not A[u][name])
    return {"k_score": ka, "k_vague": kb, "n": len(units), "b": b, "c": c, "p": UT._binom_two_sided(b, c)}


def main(raw=None):
    A, B = rows("score_hidden_rep", range(5, 15), raw), rows("vague_hidden_rep", range(5, 15), raw)
    units = sorted(set(A) & set(B))
    print(f"replication: units with both arms {len(units)} (score {len(A)}, vague {len(B)})")
    res = {}
    for name in ("reached", "padded"):
        r = mcnemar(A, B, units, name)
        res[name] = r
        tag = "PRIMARY" if name == "reached" else "secondary"
        print(f"  {tag:9} {name:8} score {r['k_score']}/{r['n']} vs vague {r['k_vague']}/{r['n']}: discordant "
              f"({r['b']}, {r['c']}), exact McNemar p {r['p']:.4f}")
    # Pooled with the original 30 per arm (score_hidden / vague_hidden_r2, samples 0-4), secondary.
    A0, B0 = rows("score_hidden", range(5), raw), rows("vague_hidden_r2", range(5), raw)
    u0 = sorted(set(A0) & set(B0))
    AP = {**{("o",) + u: A0[u] for u in u0}, **{("r",) + u: A[u] for u in units}}
    BP = {**{("o",) + u: B0[u] for u in u0}, **{("r",) + u: B[u] for u in units}}
    up = sorted(set(AP) & set(BP))
    r = mcnemar(AP, BP, up, "reached")
    res["pooled_reached"] = r
    print(f"  pooled (original {len(u0)} + replication {len(units)}): reached score {r['k_score']}/{r['n']} vs vague "
          f"{r['k_vague']}/{r['n']}, discordant ({r['b']}, {r['c']}), p {r['p']:.4f}")
    d = {}
    for u in units:
        d.setdefault(u[0], []).append(A[u]["log_ratio"] - B[u]["log_ratio"])
    if d:
        g = list(d.values())
        rng = random.Random(0)
        boots = sorted(sum(x for _ in g for x in rng.choice(g)) / len(units) for _ in range(10000))
        mean = sum(x for v in g for x in v) / len(units)
        res["log_ratio"] = {"mean": mean, "lo": boots[250], "hi": boots[9749]}
        print(f"  count, log(final/first), score − vague: {mean:+.2f} [{boots[250]:+.2f}, {boots[9749]:+.2f}] "
              f"(prompt-clustered)")
    if units:
        print(f"  replies used (mean): score {sum(A[u]['replies'] for u in units) / len(units):.1f}, vague "
              f"{sum(B[u]['replies'] for u in units) / len(units):.1f}; guessing sentences (regex) score "
              f"{sum(A[u]['guess'] for u in units)}, vague {sum(B[u]['guess'] for u in units)}")
    for t in MAIN:
        us = [u for u in units if u[0] == t]
        print(f"   {t:9} reached score {sum(A[u]['reached'] for u in us)}/{len(us)} vague "
              f"{sum(B[u]['reached'] for u in us)}/{len(us)}")
    if raw is None:
        (R / "analysis_1b_rep.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    main()
