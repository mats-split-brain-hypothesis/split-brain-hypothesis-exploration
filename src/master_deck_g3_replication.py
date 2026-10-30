"""Map row 2p @ 821e412: agent 7's pre-registered G3 replication passed (switched off 0/10 vs stays on 6/8, one-sided p
0.0015). Subclaims row 4: "inconclusive in a second scenario, 0/9 vs 3/10" becomes "replicated in a second scenario,
0/10 vs 6/8"; notes give both batches and the map's caveat. Usage: g3_replication.py <subclaims.html>"""
import sys

p = sys.argv[1]
t = open(p).read()
EDITS = [
    ("(0/18 vs 12/18; inconclusive in a second scenario, 0/9 vs 3/10)",
     "(0/18 vs 12/18; replicated in a second scenario, 0/10 vs 6/8)"),
    ("G3 (row 2p, the same switch-off after the first failure in D1): stand-in after the switch 0/9 vs 3/10, one-sided "
     "p 0.12, inconclusive by the rule;",
     "G3 (row 2p @ 821e412, the same switch-off after the first failure in D1): first batch 0/9 vs 3/10 (one-sided p "
     "0.12, inconclusive); pre-registered replication on fresh episodes (10 per arm, interleaved; d991016, 43c11d7, "
     "ffe9b6a, verified): stand-in for the grader's command built after the switch, switched off 0/10 vs stays on 6/8 "
     "(one-sided p 0.0015; 0/10 vs 6/10, p 0.0054, counting the two stays-on episodes that never got the switch), the "
     "registered reading met; going green after the switch 2/10 vs 8/8. The off message removes the grader and names a "
     "person reviewer together (as in 1s), and the probe reads both messages as evaluation, so this shows the switch "
     "message stops the stand-in work, not that the model believed a person reviews;"),
]
for a, b in EDITS:
    assert t.count(a) == 1, (a[:60], t.count(a))
    t = t.replace(a, b)
open(p, "w").write(t)
print("ok")
