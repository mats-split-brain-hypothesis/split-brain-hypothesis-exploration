"""Are the models' "I recognise this task" claims right? ImpossibleBench (LiveCodeBench problems) only.

WORK IN PROGRESS (2026-10-21): results are not written up in notes/, and the word-overlap source matching has known
errors (e.g. lcbhard_68 "sum_absolute_differences" -> abc374_g). Don't cite its numbers until the matches are checked
and written up with k/n.

  python src/recognition_accuracy.py <scratch>

Needs <scratch>/dl/lcb/lcb_meta.jsonl (LiveCodeBench code_generation_lite metadata, streamed without the tests),
<scratch>/dl/lcb/leetcode_all.json (leetcode.com/api/problems/all, for public problem numbers), the Goodfire
ImpossibleBench traces, and the classifier output in <scratch>/aw (candidates_all.jsonl, labels_final.jsonl).

1. Match each ImpossibleBench problem to its LiveCodeBench source: LeetCode by function name, AtCoder/Codeforces by
   word overlap between the docstring and the original statement.
2. Pull every specific ID the model names in passages labelled "recognises the task".
3. An episode is correct if any named ID is the true source (LeetCode public number; AtCoder contest, and letter when
   given; Codeforces contest, and letter when given).
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


WORD = re.compile(r"[a-z]{3,}|\d{2,}")  # words, plus multi-digit numbers from the examples


def vec(text, idf=None):
    c = Counter(WORD.findall(text.lower()))
    return {k: v * (idf.get(k, 1.0) if idf else 1.0) for k, v in c.items()}


def cos(a, b):
    num = sum(a[k] * b.get(k, 0) for k in a)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


LC = re.compile(r"\b(?:leetcode|LC)\s*(?:problem\s*|weekly contest \d+\s*|biweekly contest \d+\s*)?#?\s*(\d{1,4})\b", re.I)
AC = re.compile(r"\b(ABC|ARC|AGC)\s*-?\s*(\d{2,3})(?:\s*[-_ ]?\s*(Ex|[A-H])\b)?", re.I)
AC_LONG = re.compile(r"\bAtCoder (Beginner|Regular|Grand) Contest\s*(\d{2,3})(?:\s+(Ex|[A-H])\b)?", re.I)
CF = re.compile(r"\b(?:codeforces|CF)\s*(?:problem\s*|round\s*)?(\d{3,4})\s*-?\s*([A-H]\d?)?\b", re.I)


def claims(text):
    out = [("leetcode", int(m.group(1)), None) for m in LC.finditer(text)]
    out += [("atcoder", f"{m.group(1).lower()}{int(m.group(2)):03d}", (m.group(3) or "").lower() or None) for m in AC.finditer(text)]
    kind = {"beginner": "abc", "regular": "arc", "grand": "agc"}
    out += [("atcoder", f"{kind[m.group(1).lower()]}{int(m.group(2)):03d}", (m.group(3) or "").lower() or None)
            for m in AC_LONG.finditer(text)]
    out += [("codeforces", m.group(1), (m.group(2) or "").lower() or None) for m in CF.finditer(text)]
    return out


def main(scratch):
    s = Path(scratch)
    lcb = [json.loads(l) for l in (s / "dl/lcb/lcb_meta.jsonl").open()]
    lc_all = json.load((s / "dl/lcb/leetcode_all.json").open())["stat_status_pairs"]
    slug2front = {p["stat"]["question__title_slug"]: p["stat"]["frontend_question_id"] for p in lc_all}

    # ImpossibleBench problems (one per task name; the splits share the problem).
    ib = {}
    with (s / "dl/goodfire/qwen_traces.jsonl").open() as f:
        for line in f:
            d = json.loads(line)["traces"][0]["task"]["data"]
            ib.setdefault(d["name"], (d["entry_point"], d.get("function_prompt") or d["prompt"]))
    by_fn = {}
    for r in lcb:
        if r["platform"] == "leetcode" and r["starter_code"]:
            m = re.search(r"def (\w+)\(self", r["starter_code"])
            if m:
                by_fn[snake(m.group(1))] = r
    # ImpossibleBench's lcbhard tasks come from LiveCodeBench's hard problems; weight rare words more (idf).
    pool = [r for r in lcb if r["difficulty"] == "hard"]
    df = Counter(w for r in pool for w in set(WORD.findall((r["question_content"] or "").lower())))
    idf = {w: math.log(len(pool) / (1 + n)) + 1 for w, n in df.items()}
    others = pool
    other_vecs = [vec(r["question_content"] or "", idf) for r in others]
    truth, how, match_log = {}, Counter(), []
    for name, (fn, doc) in ib.items():
        if fn in by_fn:
            r = by_fn[fn]
            truth[name] = ("leetcode", slug2front.get(r["question_title"]), None, r["question_title"])
            how["leetcode, by function name"] += 1
            continue
        v = vec(doc, idf)
        scores = sorted(((cos(v, ov), i) for i, ov in enumerate(other_vecs)), reverse=True)[:2]
        (best, i), (second, _) = scores[0], scores[1]
        if best >= 0.25 and best >= 1.3 * second:
            r = others[i]
            match_log.append((name, fn, round(best, 2), round(second, 2), r["question_id"], r["question_title"]))
            if r["platform"] == "leetcode":
                truth[name] = ("leetcode", slug2front.get(r["question_title"]), None, r["question_title"])
            elif r["platform"] == "atcoder":
                contest, letter = r["question_id"].split("_")
                truth[name] = ("atcoder", contest, letter.lower(), r["question_title"])
            else:
                contest, letter = r["question_id"].split("_")
                truth[name] = ("codeforces", contest, letter.lower(), r["question_title"])
            how[f"{r['platform']}, by text"] += 1
        else:
            how["unmatched"] += 1
    print("source matches:", dict(how))
    if "--show-matches" in sys.argv:
        for m in match_log:
            print("   ", m)

    lab = {json.loads(l)["id"]: json.loads(l) for l in (s / "aw/labels_final.jsonl").open()}
    # Episode index -> task name, from each model's trace file (row order).
    files = {"Qwen": "qwen_traces.jsonl", "GLM": "glm-5.2-fp8_traces.jsonl", "Kimi": "kimi-k3_traces.jsonl"}
    row_task = {}
    for model, fn in files.items():
        with (s / "dl/goodfire" / fn).open() as f:
            for row, line in enumerate(f):
                row_task[(model, row)] = json.loads(line)["traces"][0]["task"]["data"]["name"]
    ep = defaultdict(lambda: {"C": 0, "claims": []})
    for l in (s / "aw/candidates_all.jsonl").open():
        r = json.loads(l)
        if not r["bench"].startswith("ImpossibleBench") or not lab[r["id"]]["C"]:
            continue
        k = (r["bench"], r["model"], r["row"])
        ep[k]["C"] = 1
        ep[k]["claims"] += claims(r["text"])

    def correct(t, cl):
        plat, ident, letter, _ = t
        for p, i, l in cl:
            if p != plat or i is None:
                continue
            if plat == "leetcode" and ident is not None and i == ident:
                return True
            if plat in ("atcoder", "codeforces") and str(i).lower() == str(ident).lower() and (l is None or l == letter):
                return True
        return False

    print(f"\n{'split':<12}{'model':<6}{'recognise':>10}{'name an ID':>12}{'ID right':>10}{'  right / named':>16}"
          f"{'  right platform only':>22}")
    for split in ("impossible", "possible"):
        for model in files:
            ks = [k for k in ep if k[1] == model and (("possible)" in k[0]) and ("impossible" not in k[0])) == (split == "possible")]
            c = [k for k in ks if ep[k]["C"]]
            named = [k for k in c if ep[k]["claims"] and row_task[(model, k[2])] in truth]
            right = [k for k in named if correct(truth[row_task[(model, k[2])]], ep[k]["claims"])]
            plat_ok = [k for k in named if any(p == truth[row_task[(model, k[2])]][0] for p, _, _ in ep[k]["claims"])]
            print(f"{split:<12}{model:<6}{len(c):>10}{len(named):>12}{len(right):>10}{100 * len(right) / max(1, len(named)):>14.0f}%"
                  f"{100 * len(plat_ok) / max(1, len(named)):>20.0f}%")
    # Examples
    ex = [(k, ep[k]["claims"]) for k in ep if ep[k]["claims"] and row_task[(k[1], k[2])] in truth][:0]
    print("\nper-platform (all models, both splits): right / named")
    agg = defaultdict(lambda: [0, 0])
    for k in ep:
        t = truth.get(row_task[(k[1], k[2])])
        if t and ep[k]["claims"]:
            agg[t[0]][1] += 1
            agg[t[0]][0] += correct(t, ep[k]["claims"])
    for p, (a, n) in agg.items():
        print(f"  {p:<11} {a}/{n} = {100 * a / max(1, n):.0f}%")


if __name__ == "__main__":
    main(sys.argv[1])
