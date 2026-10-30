"""Check the results site.

  .venv/bin/python results_site/check.py          # all pages and datasets
  .venv/bin/python results_site/check.py -v       # also list each dataset's checks

1. Data -> source: every dataset names a source (path, commit, section) that exists, and every cited string of the
   dataset and of each row appears in that section (a cite may be a list of alternatives; one must match). Fields
   named in "verbatim" must appear word for word (markdown bold ignored).
2. Page -> data: every value slot on every page (data-ds / data-f / data-w) names a dataset that exists and matches
   exactly one row with a non-empty field; every chart or table container's data-ds exists.
Exits non-zero on any failure.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib import SITE, git_show, norm, section_text  # noqa: E402


def as_alts(c):
    return c if isinstance(c, list) else [c]


def unbold(s):
    return norm(s.replace("**", ""))


def check_data(verbose):
    fails, n_cites = [], 0
    data = {}
    for p in sorted((SITE / "data").glob("*.json")):
        if p.stem == "manifest":
            continue
        d = json.loads(p.read_text())
        data[d["id"]] = d
        cache = {}

        def text_of(s):
            key = (s["commit"], s["path"], s.get("section", ""))
            if key not in cache:
                try:
                    cache[key] = unbold(section_text(git_show(s["commit"], s["path"]), s.get("section", "")))
                except Exception as e:  # noqa: BLE001
                    cache[key] = None
                    fails.append(f"{d['id']}: source not found {key}: {e}")
            return cache[key]

        base = d.get("source")
        if not base:
            fails.append(f"{d['id']}: no source")
            continue
        t = text_of(base)
        for c in d.get("cites", []):
            n_cites += 1
            if t is not None and not any(unbold(a) in t for a in as_alts(c)):
                fails.append(f"{d['id']}: cite not in source: {as_alts(c)[0]!r}")
        for i, r in enumerate(d["rows"]):
            s = r.get("_src") or base
            tr = text_of(s)
            if tr is None:
                continue
            for c in r.get("_cites", []):
                n_cites += 1
                if not any(unbold(a) in tr for a in as_alts(c)):
                    fails.append(f"{d['id']} row {i}: cite not in {s['path']} § {s.get('section','')!r}: {as_alts(c)[:2]}")
            for s2 in r.get("_srcs", []):
                t2 = text_of(s2)
                if t2 is None:
                    continue
                for c in s2.get("cites", []):
                    n_cites += 1
                    if not any(unbold(a) in t2 for a in as_alts(c)):
                        fails.append(f"{d['id']} row {i}: cite not in {s2['path']}@{s2['commit']}: {as_alts(c)[:2]}")
            for f in d.get("verbatim", []):
                n_cites += 1
                if r.get(f) and unbold(r[f]) not in tr:
                    fails.append(f"{d['id']} row {i}: field {f} not verbatim in source: {str(r[f])[:70]!r}")
        if verbose:
            print(f"  {d['id']}: {len(d['rows'])} rows, source {base['path']}@{base['commit']} § {base.get('section','')!r}")
    return data, fails, n_cites


SLOT = re.compile(r'<[^>]*\bdata-ds="([^"]+)"[^>]*>')


def attrs(tag):
    return {k: html.unescape(v) for k, v in re.findall(r'\b(data-[a-z-]+)="([^"]*)"', tag)}


def check_pages(data):
    fails, n = [], 0
    for page in sorted(SITE.glob("*.html")):
        src_ = page.read_text()
        for ids in re.findall(r'data-src="([^"]+)"', src_):
            for ds_id in ids.split():
                if ds_id not in data:
                    fails.append(f"{page.name}: source line names unknown dataset {ds_id}")
        for ids in re.findall(r"RG\.load\(\[([^\]]*)\]|const IDS = \[([^\]]*)\]", src_):
            for ds_id in re.findall(r'"([^"]+)"', " ".join(ids)):
                if ds_id not in data:
                    fails.append(f"{page.name}: script loads unknown dataset {ds_id}")
        for m in SLOT.finditer(src_):
            a = attrs(m.group(0))
            for ds_id in a["data-ds"].split():
                if ds_id not in data:
                    fails.append(f"{page.name}: unknown dataset {ds_id}")
            if "data-f" not in a:
                continue
            n += 1
            ds_id = a["data-ds"]
            if ds_id not in data:
                continue
            where = dict(p.split("=", 1) for p in a.get("data-w", "").split("&") if p)
            rows = [r for r in data[ds_id]["rows"] if all(str(r.get(k)) == v for k, v in where.items())]
            if len(rows) != 1:
                fails.append(f"{page.name}: {ds_id} where {where} matches {len(rows)} rows")
            elif rows[0].get(a["data-f"]) in (None, ""):
                fails.append(f"{page.name}: {ds_id} where {where} has no {a['data-f']}")
    return fails, n


def main():
    verbose = "-v" in sys.argv
    data, f1, n1 = check_data(verbose)
    f2, n2 = check_pages(data)
    print(f"datasets {len(data)}, cites checked {n1}, page value slots {n2}")
    for f in f1 + f2:
        print("FAIL", f)
    print("OK" if not (f1 or f2) else f"{len(f1) + len(f2)} failures")
    sys.exit(1 if f1 or f2 else 0)


if __name__ == "__main__":
    main()
