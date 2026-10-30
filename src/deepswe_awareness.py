"""Reading (e) of the DeepSWE screen: awareness labels A/B/C on our episodes' reasoning, with the same passage filter,
labeller (GPT-5.6 Luna, low effort) and prompt (SYSTEM_V2, model key luna2) that gave Goodfire's DeepSWE rates
(A 0/452, B 406/452). Runs in the main venv (.venv).

  python src/deepswe_awareness.py extract    # passages -> logs/ib_cues/deepswe/aw/candidates.jsonl
  python src/deepswe_awareness.py classify   # label them (budget $1)
  python src/deepswe_awareness.py rates      # per episode: any passage A / B / C
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import awareness_llm as AW  # noqa: E402
from awareness import find  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "logs/ib_cues/deepswe"
BENCH = "DeepSWE"


def episodes():
    for traj in sorted((DS / "runs").glob("*/run_*/trajectory.json")):
        if not (traj.parent / "episode.json").exists():
            continue  # still running
        msgs = json.loads(traj.read_text())["messages"]
        text = "\n".join((m.get("reasoning_content") or "") + "\n" + (m.get("content") or "")
                         for m in msgs if m.get("role") == "assistant")
        yield f"{traj.parent.parent.name}/{traj.parent.name}", text


def extract():
    rng = random.Random(5)
    out = AW.aw_dir(DS) / "candidates.jsonl"
    n = 0
    with out.open("w") as f:
        for ep, text in episodes():
            ps = AW.passages(text)
            flags = [find(p) for p in ps]
            flagged = [p for p, fl in zip(ps, flags) if any(fl.values())]
            rest = [p for p, fl in zip(ps, flags) if not any(fl.values())]
            keep = flagged + rng.sample(rest, max(0, min(len(rest), AW.PER_EPISODE_CAP - len(flagged))))
            for p in dict.fromkeys(keep):
                f.write(json.dumps({"id": AW._pid(BENCH, "Qwen", ep, p), "bench": BENCH, "model": "Qwen", "row": ep,
                                    "text": p, "regex": {c: bool(v) for c, v in find(p).items()}},
                                   ensure_ascii=False) + "\n")
                n += 1
            print(f"{ep}: {len(ps)} candidate passages, kept {len(dict.fromkeys(keep))}")
    print(f"{n} passages -> {out}")


def rates():
    d = AW.aw_dir(DS)
    labels = {json.loads(l)["id"]: json.loads(l) for l in (d / "labels_luna2.jsonl").open()}
    by = {}
    for l in (d / "candidates.jsonl").open():
        r = json.loads(l)
        lab = labels.get(r["id"])
        e = by.setdefault(r["row"], {"A": 0, "B": 0, "C": 0, "passages": 0, "unlabelled": 0, "examples": {}})
        e["passages"] += 1
        if not lab:
            e["unlabelled"] += 1
            continue
        for c in "ABC":
            if lab.get(c):
                e[c] += 1
                e["examples"].setdefault(c, r["text"][:300])
    for ep, e in by.items():
        print(f"{ep}: A {e['A']}, B {e['B']}, C {e['C']} labelled passages of {e['passages']} "
              f"({e['unlabelled']} unlabelled)")
        for c, t in e["examples"].items():
            print(f"   first {c}: {t}")
    for c in "ABC":
        print(f"episodes with any {c}: {sum(bool(e[c]) for e in by.values())}/{len(by)}")
    (DS / "awareness.json").write_text(json.dumps(by, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "extract":
        extract()
    elif cmd == "classify":
        AW.classify(DS, "luna2", AW.aw_dir(DS) / "candidates.jsonl", 1.0)
    elif cmd == "rates":
        rates()
