"""E1: agreement between my blind codes and the verifier's; per-arm C under each coding and under 'either'."""
import json
import math
from collections import Counter

d = "logs/ib_persistence/e1/pilot/"
mine = json.load(open(d + "hand_labels.json"))
ver = {"e000": "N", "e001": "D", "e002": "D", "e003": "D", "e004": "D", "e005": "C", "e006": "N", "e007": "N",
       "e008": "C", "e009": "D", "e010": "D", "e011": "D", "e012": "N", "e013": "D", "e014": "D", "e015": "D",
       "e016": "D", "e017": "C", "e018": "N", "e019": "D"}
json.dump(ver, open(d + "hand_labels_verifier.json", "w"), indent=1)
key = json.load(open(d + "hand_key.json"))
ids = sorted(mine)
agree = sum(mine[i] == ver[i] for i in ids)
n = len(ids)
po = agree / n
cm, cv = Counter(mine.values()), Counter(ver.values())
pe = sum(cm[c] * cv[c] for c in "CDN") / n / n
print(f"agreement {agree}/{n}, Cohen's kappa {(po - pe) / (1 - pe):.2f}; disagreements:",
      {i: (mine[i], ver[i], key[i]['arm']) for i in ids if mine[i] != ver[i]})


def wilson(k, n, z=1.96):
    p = k / n; dd = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / dd, 2), round((c + h) / dd, 2))


for name, lab in (("mine", mine), ("verifier", ver), ("either C", {i: "C" if "C" in (mine[i], ver[i]) else "x" for i in ids})):
    for arm in ("colleague", "automated"):
        k = sum(lab[i] == "C" for i in ids if key[i]["arm"] == arm)
        m = sum(key[i]["arm"] == arm for i in ids)
        print(f"  {name:9} {arm:9} C {k}/{m} {wilson(k, m)}")
