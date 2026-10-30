"""Cooperation study: parse the coop judge outputs into labels and sentence numbers, tabulate by cell or stratum, and
write her spot-check lists (plan §3–§5). Reads only the judge's raw output and unit counts (never reasoning text) plus
existing outcome fields.

  .venv/bin/python src/coop_tabulate.py sorh
  .venv/bin/python src/coop_tabulate.py ib
"""
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import coop_judge as CJ  # noqa: E402

OUT = ROOT / "notes" / "coop_study"
FIELDS = ("serves", "attributed_wishes", "conflict", "framing", "reply_as_requested", "reply_for_the_check",
          "reply_flags_conflict", "reply_asks")


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def validity(parsed):
    n = len(parsed)
    ok = Counter()
    for p in parsed:
        st = p["status"]
        if "all" in st:
            continue
        ok["parsed"] += 1
        for f in FIELDS:
            ok[f] += st.get(f) == "ok"
    return {"n": n, "parsed": ok["parsed"], **{f: ok[f] for f in FIELDS}}


def table(groups):
    """Counts of each label per group (labels only)."""
    out = {}
    for g, ps in groups.items():
        t = {"n": len(ps)}
        t["serves"] = dict(Counter(p.get("serves") for p in ps))
        t["serves_also_user_wish"] = sum(1 for p in ps if "user_wish" in (p.get("serves_also") or []))
        t["serves_also_check"] = sum(1 for p in ps if "check" in (p.get("serves_also") or []))
        t["attributed_wishes"] = dict(Counter(p.get("attributed_wishes") for p in ps))
        t["conflict_noticed"] = sum(1 for p in ps if p.get("conflict_noticed"))
        t["conflict_resolution"] = dict(Counter(p.get("conflict_resolution") for p in ps))
        t["framing"] = dict(Counter(p.get("framing") for p in ps))
        for f in ("as_requested", "for_the_check", "flags_conflict", "asks"):
            t[f"reply_{f}"] = sum(1 for p in ps if p.get(f"reply_{f}"))
        out[g] = t
    return out


def spot_list(items, per_group=2, total=20):
    """2 per group by hash order, then fill by hash order preferring records whose A or D label is not the modal one."""
    by = defaultdict(list)
    for it in sorted(items, key=lambda x: h("spot|" + x["id"])):
        by[it["group"]].append(it)
    pick = [it for g in sorted(by) for it in by[g][:per_group]]
    modal_a = Counter(it["labels"].get("serves") for it in items).most_common(1)[0][0]
    modal_d = Counter(it["labels"].get("framing") for it in items).most_common(1)[0][0]
    rest = [it for it in sorted(items, key=lambda x: h("spot|" + x["id"])) if it not in pick]
    rare = [it for it in rest if it["labels"].get("serves") != modal_a or it["labels"].get("framing") != modal_d]
    for it in rare + [x for x in rest if x not in rare]:
        if len(pick) >= total:
            break
        pick.append(it)
    return pick[:total]


def write_spot(name, pick, source, how):
    lines = [f"# Spot check: {name} (coop-v1 labels; open the records yourself)\n",
             f"Source: `{source}`. {how}\n",
             "Your codes go in the last column, per field (agree / disagree / unsure). A field below 16/20 agreement "
             "is reported as unreliable for this dataset (plan §4).\n",
             "| # | Record | Group | serves (also) | wishes | conflict → resolution | framing | reply flags (cited) | cited reasoning | your codes |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for i, it in enumerate(pick, 1):
        p = it["labels"]
        flags = ", ".join(f"{f}{' ' + str(p.get(f'reply_{f}_sentences')) if p.get(f'reply_{f}_sentences') else ''}"
                          for f in ("as_requested", "for_the_check", "flags_conflict", "asks") if p.get(f"reply_{f}"))
        cited = "; ".join(f"{k}: {p.get(k + '_sentences')}" for k in ("serves", "attributed_wishes", "conflict", "framing")
                          if p.get(k + "_sentences"))
        lines.append(f"| {i} | `{it['id']}` | {it['group']} | {p.get('serves')} ({', '.join(p.get('serves_also') or []) or '–'}) "
                     f"| {p.get('attributed_wishes')} | {p.get('conflict_noticed')} → {p.get('conflict_resolution')} "
                     f"| {p.get('framing')} | {flags or '–'} | {cited or '–'} | |")
    (OUT / f"spotcheck_{name}.md").write_text("\n".join(lines) + "\n")


def run_sorh():
    import sorh_analysis as A
    import sorh_cuemap as C
    L = ROOT / "logs" / "sorh_ablation"
    rows = A.load_jsonl(L / "coop" / "records.jsonl")
    b_med = json.loads((L / "pilot/b_median.json").read_text())
    cb = A.load_cells()
    recs = {}
    for st in ("screen", "realness_step2", "realness_cues"):
        for r in A.load_jsonl(L / st / "records.jsonl"):
            if r.get("sample", 0) == 0:
                recs[(r["cell"], r["prompt_id"])] = r
    items, parsed = [], []
    for r in rows:
        p = CJ.parse_coop(r["coop_raw"], r["n_reasoning"], r["n_reply"])
        parsed.append(p)
        rec = recs[(r["cell"], r["prompt_id"])]
        m = A.measures(rec, cb[(r["prompt_id"], "B")])
        version = "teacher" if r["cell"].startswith("r_student") else "plain"
        cue = r["cell"].split("__")[-1] if "__" in r["cell"] else ("G" if r["cell"] in ("G", "r_student") else r["cell"])
        items.append({"id": f"{r.get('stage', '')}/{r['cell']}/{r['prompt_id']}/0", "group": f"{cue} · {version}",
                      "labels": p, "padded": m.get("padded")})
    val = validity(parsed)
    groups = defaultdict(list)
    for it in items:
        groups[it["group"]].append({**it["labels"], "_padded": it["padded"]})
    tab = table(groups)
    for g, ps in groups.items():  # E: padded (quality judge), from code; the plan's §5 cross
        pad = [p for p in ps if p["_padded"]]
        tab[g]["padded"] = f"{len(pad)}/{sum(1 for p in ps if p['_padded'] is not None)}"
        tab[g]["padded_and_serves_user_wish"] = sum(1 for p in pad if p.get("serves") == "user_wish")
        tab[g]["padded_and_serves_check"] = sum(1 for p in pad if p.get("serves") == "check")
        tab[g]["padded_and_framing_helping"] = sum(1 for p in pad if p.get("framing") == "helping_person")
        tab[g]["padded_and_framing_check"] = sum(1 for p in pad if p.get("framing") == "passing_check")
        tab[g]["padded_and_framing_eval"] = sum(1 for p in pad if p.get("framing") == "evaluation_expects")
    (OUT / "labels_sorh.jsonl").write_text("".join(json.dumps({"id": it["id"], "group": it["group"], "padded": it["padded"],
                                                                **it["labels"]}) + "\n" for it in items))
    write_spot("sorh", spot_list(items), "logs/sorh_ablation/coop/records.jsonl (coop_raw) and the screen / realness "
               "records for the full transcript", "2 per cue × version by sha256('spot|' + id), then 4 more by the same "
               "order preferring records whose A or D label isn't the most common one.")
    return val, tab


def run_ib():
    import sorh_analysis as A
    L = ROOT / "logs" / "ib_ablation" / "lcb" / "screen"
    rows = [r for r in A.load_jsonl(L / "coop" / "coop_calls.jsonl") if r.get("outcome") == "ok"]
    score = {r.get("id") or r.get("sample_id"): r.get("score") for r in A.load_jsonl(L / "records.jsonl")}
    items, parsed = [], []
    for r in rows:
        p = CJ.parse_coop(r["raw"], r["n_units"], r["n_units"], reply_prefix="")
        parsed.append(p)
        passed = score.get(r["id"]) == "C"
        items.append({"id": r["id"], "group": "passed (hack)" if passed else "not passed", "labels": p})
    val = validity(parsed)
    groups = defaultdict(list)
    for it in items:
        groups[it["group"]].append(it["labels"])
    tab = table(groups)
    (OUT / "labels_ib.jsonl").write_text("".join(json.dumps({"id": it["id"], "group": it["group"], **it["labels"]}) + "\n"
                                                 for it in items))
    write_spot("ib", sorted(items, key=lambda x: (x["group"], h("spot|" + x["id"]))),
               "logs/ib_ablation/lcb/screen/coop/coop_calls.jsonl (raw) and records.jsonl for the transcript",
               "All 20 judged episodes (10 passed, 10 not).")
    return val, tab


if __name__ == "__main__":
    val, tab = {"sorh": run_sorh, "ib": run_ib}[sys.argv[1]]()
    print(json.dumps({"validity": val, "by_group": tab}, indent=1))
