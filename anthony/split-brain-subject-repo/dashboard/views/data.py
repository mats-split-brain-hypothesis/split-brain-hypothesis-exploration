"""Shared data: what the shared Hugging Face dataset holds and where each result came from. Read from its manifest
(jlm.hfdata, one small file), so it costs nothing to open. Every pipeline step pushes its outputs as it finishes
(``hfdata.share``), from whichever branch it ran on; the dashboard pulls them every few minutes (dashboard/hfsync.py)."""

from collections import defaultdict
from datetime import datetime

import streamlit as st

import catalog
import hfsync
import ui
from jlm import hfdata

ui.page_header("Project", "Shared data",
               "Everything here was pushed to the shared dataset by a pipeline step (evaluate, judge, analyse, capture, "
               "generation) on someone's branch. The dashboard pulls new results every 5 minutes; the sidebar shows the "
               "last pull.")

rid = hfsync.repo()
if not rid:
    st.info("No shared dataset configured (env JLM_HF_DATASET or hfdata.REPO).")
    st.stop()
files = hfdata.remote_files(rid, refresh=st.button("Refresh", icon=":material/refresh:"))
if not files:
    st.warning(f"`{rid}` is not reachable from here (no token, offline) or still empty.")
    st.stop()


def when(t: str) -> str:
    try:
        return datetime.fromisoformat(t).strftime("%d %b %H:%M")
    except (TypeError, ValueError):
        return t or "–"


def size(n: float) -> str:
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


# ------------------------------------------------------------------ what is there
tops = defaultdict(lambda: [0, 0, ""])
for rel, e in files.items():
    t = tops[rel.split("/")[0]]
    t[0], t[1], t[2] = t[0] + 1, t[1] + e.get("size", 0), max(t[2], e.get("time", ""))
st.html(f'<div class="jm-cap">Dataset <a href="https://huggingface.co/datasets/{rid}" target="_blank"><code>{rid}</code></a> · '
        f"{len(files)} files · " + " · ".join(f"<b>{d}</b> {n} ({size(b)})" for d, (n, b, _) in sorted(tops.items())) + "</div>")

# ------------------------------------------------------------------ results, newest first
runs = {}  # (kind, where, what) -> newest entry among its files
for rel, e in files.items():
    parts = rel.split("/")
    if parts[0] in ("eval", "screen") and len(parts) >= 5:
        key = ("judged" if parts[4].startswith("judged") else "arm", f"{parts[1]}/{parts[2]}", parts[3])
        if key[0] == "judged":
            key = ("judged", f"{parts[1]}/{parts[2]}", f"{parts[3]} · {parts[4]}")
    elif parts[0] == "analysis" and len(parts) >= 3:
        key = ("study", parts[1], "battery")
    elif parts[0] == "captures":
        key = ("capture", "captures", parts[-1].removesuffix(".provenance.json").removesuffix(".pt"))
    else:
        continue
    if key not in runs or e.get("time", "") > runs[key].get("time", ""):
        runs[key] = e

people = sorted({e.get("by", "?") for e in runs.values()})
branches = sorted({(e.get("git") or "?").split("@")[0] for e in runs.values()})
c1, c2, c3 = st.columns([1.2, 1.4, 2])
who = c1.multiselect("Pushed by", people, default=people, key="data_who")
br = c2.multiselect("Branch", branches, default=branches, key="data_branch")
kinds = c3.segmented_control("Show", ["arm", "judged", "study", "capture"], selection_mode="multi",
                             default=["arm", "judged", "study"], key="data_kinds") or []
rows = [(k, e) for k, e in runs.items() if k[0] in kinds and e.get("by", "?") in who and (e.get("git") or "?").split("@")[0] in br]
rows.sort(key=lambda r: r[1].get("time", ""), reverse=True)
ui.label("Latest results", f"{len(rows)} of {len(runs)} · newest first")
ui.table(["when", "what", "where", "arm / run", "pushed by", "branch @ commit"],
         [[when(e.get("time")), k[0], ui.esc(k[1]), ui.esc(catalog.from_dir(k[2]) if k[0] == "arm" else k[2]), ui.esc(e.get("by", "?")),
           f"<code>{ui.esc(e.get('git', '?'))}</code>"] for k, e in rows[:300]],
         mono={2, 3})
if len(rows) > 300:
    st.caption(f"{len(rows) - 300} older entries not shown.")
