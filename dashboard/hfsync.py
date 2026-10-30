"""Keep the dashboard's out/ in step with the shared Hugging Face dataset (jlm.hfdata; notes/eval-pipeline.md,
"Shared data on Hugging Face"), so whoever opens it sees every result anyone has pushed.

- Results (``RESULTS``: eval, analysis, concept-labels, screen) are pulled in a background thread when the server
  starts and every ``EVERY`` seconds after, never blocking a page; the next rerun reads what arrived (the loaders'
  caches key on file mtimes).
- Captures (gigabytes; only "Centres in detail" and "Means / g compared" read them) are fetched on demand, file by
  file, through ``need_captures``.
- Without a configured repo (env ``JLM_HF_DATASET`` or ``hfdata.REPO``) or a token, everything here is a no-op and
  the dashboard shows what is local, as before.

A pull never overwrites a file changed here since the last sync, and bank summaries are merged, so running the
dashboard next to your own experiments is safe.
"""

import io
import os
import threading
import time
from contextlib import redirect_stdout
from pathlib import Path

import streamlit as st

from jlm import REPO_ROOT, hfdata

RESULTS = ["eval", "analysis", "concept-labels", "screen"]
#: A fresh server (a Space restart keeps no disk) pulls in this order, each pass skipping the patterns it names: the
#: small files the pages read (summaries, judge results, per-bank caches) within a minute, then every arm's
#: full-vocabulary readouts. Everything else (rank rows, masked and semantic readouts) is fetched by the page that
#: reads it (sources._get), never in bulk: the Hub allows about 5,000 downloads per 5 minutes, and each file is one.
HEAVY = ("*/readouts.jsonl", "*/masked.jsonl", "*/ranks.jsonl")
PASSES = [HEAVY, ("*/sem/*", "*/masked.jsonl", "*/ranks.jsonl")]
#: Never pulled in the background: read by no page (provenance, the judge's per-cell log, the analysis tensors), or
#: superseded (per-arm caches, now one file per bank).
NEVER = ("*/provenance.json", "*/cells.jsonl", "*.pt", "*/ranks.by_layer.json", "*/item_passes.json", "*/junk.by_layer.json")
WORKERS = 4  # parallel downloads: the readouts in about 10 minutes, well under the Hub's limit, leaving the pages headroom
EVERY = float(os.environ.get("JLM_HF_SYNC_EVERY", 300))  # seconds between background pulls
OUT = Path(os.environ.get("JLM_DASH_OUT") or REPO_ROOT / "out")  # the dashboard's out/ (as sources.OUT)


def repo() -> str | None:
    return hfdata.configured(required=False)


@st.cache_resource
def _state() -> dict:
    """One sync state per server process (shared by every session): the loop starts with it."""
    s = {"running": False, "last": None, "pulled": 0, "error": None, "log": "", "lock": threading.Lock()}
    if repo():
        threading.Thread(target=_loop, args=(s,), daemon=True, name="hfsync").start()
    return s


def _pull_once(s: dict) -> None:
    if not s["lock"].acquire(blocking=False):  # a pull is already running
        return
    s["running"] = True
    try:
        subs = [d for d in RESULTS if d in {r.split("/")[0] for r in hfdata.remote_files(refresh=True)}]
        buf, pulled = io.StringIO(), 0
        with redirect_stdout(buf):
            for skip in PASSES if subs else []:
                p = hfdata.pull(subs, out=OUT, skip=skip + NEVER, workers=WORKERS)
                pulled = max(pulled, len(p.where(*hfdata.PULL)))
        s["pulled"] = pulled
        s["log"], s["error"], s["last"] = buf.getvalue()[-4000:], None, time.time()
    except Exception as e:
        s["error"] = f"{type(e).__name__}: {e}"[:400]
    finally:
        s["running"] = False
        s["lock"].release()


def _loop(s: dict) -> None:
    while True:
        _pull_once(s)
        time.sleep(EVERY)


def start() -> dict:
    """Start the background pull (once per server); returns its state."""
    return _state()


def sync_now() -> None:
    threading.Thread(target=_pull_once, args=(_state(),), daemon=True).start()


def sidebar() -> None:
    """One status line under the repo state, with a button to pull now."""
    rid = repo()
    if not rid:
        st.caption("Shared data: no Hugging Face dataset configured (local `out/` only).")
        return
    s = _state()
    if s["running"]:
        when = "pulling…"
    elif s["last"]:
        mins = (time.time() - s["last"]) / 60
        when = f"synced {'just now' if mins < 1 else f'{mins:.0f} min ago'}" + (f" · {s['pulled']} new files" if s["pulled"] else "")
    else:
        when = "first pull pending"
    c1, c2 = st.columns([5, 1], vertical_alignment="center")
    c1.caption(f"Data: `{rid}` · {when}" + (f" · ⚠ {s['error']}" if s["error"] else ""))
    c2.button("", icon=":material/sync:", key="hf_sync_now", help="Pull new results from the shared dataset now",
              on_click=sync_now)


def need_captures(family: str, split: str, centre: str = "", ref: str = "") -> list[str]:
    """Fetch (if missing) the captures a centre's geometry is rebuilt from: the read bank's, and its reference set's.
    Returns the paths that are still missing (offline, or not in the dataset either)."""
    from jlm import capture

    if not repo():
        return []
    want = [f"captures/{family}-{split}.pt"]
    if ref in capture.CORPORA:
        want.append("captures/" + capture.REFS[ref.removesuffix("8")].name)
    elif ref in capture.POOLS:
        want += [r for r in hfdata.listing("captures", out=OUT) if r.endswith("-fit.pt") and "_mt" not in r]
    elif ref and ref != "self":
        want.append(f"captures/{family}-{ref}.pt")
    head = centre.split(":")[0]
    if head.startswith("gen"):
        want += [r for r in hfdata.listing("captures", out=OUT) if r.startswith(f"captures/gen-{family}-") and r.endswith(".pt")]
    elif head.startswith("glos"):
        want += [r for r in hfdata.listing("captures", out=OUT) if r.startswith("captures/glos-") and r.endswith(".pt")]
    elif head in ("dict", "cpt", "cptc", "cpt+", "cptc+"):
        want += [r for r in hfdata.listing("captures", out=OUT) if r.startswith("captures/carriers") and r.endswith(".pt")]
        want += ["captures/sents-wiki.pt"] if head == "dict" else []
    missing = []
    with st.spinner("Fetching captures from the shared dataset…"):
        for rel in dict.fromkeys(want):
            if hfdata.ensure(rel, out=OUT) is None:
                missing.append(rel)
    return missing
