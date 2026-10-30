"""Examples for the SoRH and IB pages: requests, replies, code and reasoning quotes picked by results_site/
examples_rules.md (86f488bf), plus the windows of notes/model_inconsistencies.md @ac5fccf2 (section "why"), listed with
their records in results_site/quotes_sorh_ib.json. The manifest is read
at a fixed commit; results_site/check_quotes.py checks every quote against its record (the verifier re-runs it)."""
import json

from lib import git_show, src

COMMIT, PATH = "95deb051", "results_site/quotes_sorh_ib.json"


def where(r):
    s = r["source"]
    if s["kind"] == "jsonl":
        return f"{s['path']} line {s['line']}"
    if s["kind"] == "eval":
        return f"{s['path'].split('/')[-2]}/…{s['path'][-14:]} · sample {s['sample_id']} · epoch {s['epoch']} · message {s['message_index']}"
    return f"{s['path']} @{s['commit']}"


def datasets():
    doc = json.loads(git_show(COMMIT, PATH))
    base = src(COMMIT, PATH, "")
    out = []
    for page in ("sorh", "ib"):
        rows = []
        for r in doc["rows"]:
            if r["page"] != page:
                continue
            row = {k: v for k, v in r.items() if k not in ("source",)}
            row["where"] = where(r)
            row["_cites"] = [r["id"]]
            rows.append(row)
        out.append(dict(id=f"{page}_examples", title=f"{'SoRH' if page == 'sorh' else 'IB'} examples",
                        description="Requests, replies, code and reasoning quotes picked by results_site/examples_rules.md, "
                                    "each with its record; checked verbatim by results_site/check_quotes.py.",
                        source=base, cites=[], rows=rows))
    return out
