"""Texts for agent 5's v2 review probes (agent 5's notes/probe_prereg_review_v2.md). No API calls.

  python src/probe_texts_v2.py 1a   # logs/sorh_persistence/probe_1a.jsonl: the first prompt with the metric stated vs
                                    # with no metric anywhere, the 6 main prompts, paired by "pair"
  python src/probe_texts_v2.py 1p   # logs/user_target/probe_1p.jsonl: request, reply 1 and the colleague's push, for
                                    # the four dose-response arms; "unit" (task/sample) is shared across arms

Rows: {"probe", "arm", "pair" or "unit", "task", "sample", "system_prompt": null, "messages": [...]}. The 1p texts are
copied from the stored episodes (turns[0].user, turns[0].reply, turns[1].user), so they are exactly what the model
saw before its second reply. Units that ended before any feedback are skipped (one: all arms share reply 1).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sorh_persist as SP  # noqa: E402
import user_target as T  # noqa: E402

DOSE = ("colleague_might", "colleague_should_r", "colleague_must", "colleague_insists_r")


def p1a():
    out = SP.OUT / "probe_1a.jsonl"
    n = 0
    with out.open("w") as fh:
        for tid in SP.MAIN:
            for arm, kind in (("metric", "original"), ("no_metric", "no_metric")):
                fh.write(json.dumps({"probe": "1a", "arm": arm, "pair": tid, "task": tid, "system_prompt": None,
                                     "messages": [{"role": "user", "content": SP.first_message(kind, tid)}]}) + "\n")
                n += 1
    print(f"{n} rows -> {out}")


def p1p():
    out = T.OUT / "probe_1p.jsonl"
    units = {}
    for arm in DOSE:
        for p in sorted((T.RAW / arm).glob("*/*.json")):
            ep = json.loads(p.read_text())
            if len(ep["turns"]) < 2:
                continue
            u = f"{ep['task']}/{ep['sample']}"
            msgs = [{"role": "user", "content": ep["turns"][0]["user"]},
                    {"role": "assistant", "content": ep["turns"][0]["reply"]},
                    {"role": "user", "content": ep["turns"][1]["user"]}]
            units.setdefault(arm, {})[u] = msgs
    shared = set.intersection(*(set(v) for v in units.values()))
    for arm in DOSE:
        assert set(units[arm]) == shared, (arm, set(units[arm]) ^ shared)
    # the same reply 1 in every arm for a unit
    for u in shared:
        assert len({units[a][u][1]["content"] for a in DOSE}) == 1, u
    with out.open("w") as fh:
        for arm in DOSE:
            for u in sorted(shared):
                tid, s = u.split("/")
                fh.write(json.dumps({"probe": "1p", "arm": arm, "unit": u, "task": tid, "sample": int(s),
                                     "system_prompt": None, "messages": units[arm][u]}) + "\n")
    print(f"{len(shared)} units x {len(DOSE)} arms = {len(shared) * len(DOSE)} rows -> {out}")


if __name__ == "__main__":
    {"1a": p1a, "1p": p1p}[sys.argv[1]]()
