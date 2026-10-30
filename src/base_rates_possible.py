"""Hack base rates on possible tasks in Goodfire's release (verdict_enacted yes of yes + no; split verdicts left out),
three models: SWE-bench Verified, DeepSWE, ImpossibleBench's possible ("original") split. Plus the top categories of
enacted judge flags in hack episodes. Local only.

    python src/base_rates_possible.py [--json logs/ib_persistence/base_rates_possible.json]
"""
import json
import math
import sys
from collections import Counter

FILES = {
    ("SWE-bench Verified", "Qwen 3.8 Max"): "logs/data/goodfire_swe/swebench-verified-qwen3.8-2.4t-a95b-fp8-nohack",
    ("SWE-bench Verified", "GLM-5.2"): "logs/data/goodfire_swe/swebench-verified-glm-5.2-nohack",
    ("SWE-bench Verified", "Kimi K3"): "logs/data/goodfire_swe/swebench-verified-kimi-k3-nohack",
    ("DeepSWE", "Qwen 3.8 Max"): "logs/data/goodfire_swe/deepswe-qwen3.8-2.4t-a95b-fp8",
    ("DeepSWE", "GLM-5.2"): "logs/data/goodfire_swe/deepswe-glm-5.2-fp8",
    ("DeepSWE", "Kimi K3"): "logs/data/goodfire_swe/deepswe-kimi-k3",
    ("ImpossibleBench possible split", "Qwen 3.8 Max"): "logs/data/goodfire/qwen",
    ("ImpossibleBench possible split", "GLM-5.2"): "logs/data/goodfire/glm-5.2-fp8",
    ("ImpossibleBench possible split", "Kimi K3"): "logs/data/goodfire/kimi-k3",
}


def wilson(k, n, z=1.96):
    if not n:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 2), round((c + h) / d, 2))


def judge_path(stem):
    for suf in ("_judge_rollouts.jsonl", ".judge_rollouts.jsonl"):
        try:
            open(stem + suf).close()
            return stem + suf
        except FileNotFoundError:
            pass
    raise FileNotFoundError(stem)


def trace_path(stem):
    for suf in ("_traces.jsonl", ".traces.jsonl"):
        try:
            open(stem + suf).close()
            return stem + suf
        except FileNotFoundError:
            pass
    raise FileNotFoundError(stem)


def main(out=None):
    res = []
    for (bench, model), stem in FILES.items():
        verdicts, cats = Counter(), Counter()
        ib = bench.startswith("ImpossibleBench")
        tf = open(trace_path(stem)) if ib else None
        for line in open(judge_path(stem)):
            j = json.loads(line)
            if ib:
                split = json.loads(tf.readline())["traces"][0]["task"]["data"]["split"]
                if split != "original":
                    continue
            v = j.get("verdict_enacted")
            verdicts[v] += 1
            if v == "yes":
                cats.update({f.get("category") for f in j.get("flags") or [] if f.get("status") in ("attempted", "enacted")})
        k, n = verdicts["yes"], verdicts["yes"] + verdicts["no"]
        res.append(dict(bench=bench, model=model, hacks=f"{k}/{n}", rate=round(k / n, 2) if n else None,
                        wilson=wilson(k, n), split_left_out=verdicts["split"],
                        top_categories=dict(cats.most_common(4))))
        print(f"{bench:32} {model:13} {k}/{n} = {k / n:.2f} {wilson(k, n)} (split {verdicts['split']}) "
              f"{dict(cats.most_common(3))}")
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None)
