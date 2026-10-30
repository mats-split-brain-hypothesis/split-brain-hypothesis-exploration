"""Project dashboard. Run from the repo root:

    .venv/bin/streamlit run dashboard/app.py        # http://localhost:8501

Each page is a file in dashboard/views/. To add one, write the file and list it below. Every number is
read from out/ and data/dev/ on load (dashboard/sources.py), so a new evaluate or judge run shows up on
the next reload; diagrams are in dashboard/figures.py.

Layout: every page is full width (layout="wide", no per-page max-width). Prose caps its own line length, ui.figure caps
diagrams at 1.2x their drawn size, and wide space is filled by putting related charts side by side in st.columns.
Streamlit re-runs page files but keeps imported modules: the helper modules below are reloaded here whenever their
file changes (several instances edit them while the server runs), so no restart is needed.
"""

import importlib
import sys
from pathlib import Path

import streamlit as st

HELPERS = ("catalog", "gloss", "figures", "sources", "ui", "screen", "hover")  # dependencies first: ui and sources import the others


@st.cache_resource
def _mtimes() -> dict[str, float]:
    return {}


def _reload_changed() -> None:
    seen = _mtimes()
    for name in HELPERS:
        mod = sys.modules.get(name)
        if mod is None:
            continue
        mt = Path(mod.__file__).stat().st_mtime
        if seen.get(name, mt) != mt:
            importlib.reload(mod)
        seen[name] = mt


# iteration's helpers, on their own line so the shared HELPERS line above merges cleanly with other branches'
HELPERS += ("battery", "figures_ll", "nights", "explainers")
_reload_changed()

import hfsync  # noqa: E402  (not in HELPERS: reloading it would start a second sync thread)
import sources  # noqa: E402
import ui  # noqa: E402

st.set_page_config(page_title="j-lens-mean", page_icon="◐", layout="wide")
if st.session_state.pop("_theme_changed", False):
    st.rerun()  # the theme is sent to the browser at the start of a run: start one with the new one
ui.setup()


def P(path, title, icon, **kw):
    return st.Page(f"views/{path}", title=title, icon=f":material/{icon}:", **kw)


nav = st.navigation(
    {
        "Project": [P("overview.py", "Setup", "space_dashboard", default=True),
                    P("data.py", "Shared data", "cloud_sync")],
        "Understand": [
            P("why.py", "Why centre", "center_focus_strong"),
            P("maths.py", "The mathematics", "function"),
            P("pca.py", "Removing principal components", "blur_linear"),
            P("local_lin.py", "Local linearisation (LL)", "timeline"),
            P("ll_results.py", "LL results (night 2)", "insights"),
            P("jpp_finalists.py", "J++ × our finalists", "compare"),
            P("readout_tokens.py", "Readout composition", "text_fields"),
        ],
        "Pipeline": [
            P("pipeline.py", "How the pipeline works", "account_tree"),
            P("results.py", "Results so far", "leaderboard"),
            P("constant_mu.py", "Constant μ exploration", "tune"),
        ],
        "Explore": [
            P("explorer.py", "Passage → readouts", "manage_search"),
            P("centres.py", "Centres in detail", "scatter_plot"),
            P("semantic.py", "Semantic-only readouts", "filter_alt"),
        ],
        "Overnight": [
            P("night2.py", "Night 2 (11–12 Oct)", "bedtime"),
            P("night2_scores.py", "Night 2 scores", "leaderboard"),
        ],
        "Loop": [
            P("scores.py", "Scores", "bar_chart"),
            P("leaderboard.py", "Leaderboard", "trophy"),
            P("means.py", "Means / g compared", "compare_arrows"),
            P("study.py", "Studies", "science"),
        ],
    },
    expanded=True,
)

with st.sidebar:
    st.html('<div style="font:italic 17px var(--f-display);color:var(--ink-2);padding:2px 0 4px">'
            "J<sub>l</sub> (h<sub>l</sub> − μ<sub>l</sub>)</div>")
    st.toggle("Night mode", value=ui.night(), key="night_toggle",
              on_change=lambda: ui.set_night(st.session_state["night_toggle"]))
    st.caption("Vocabulary", help="By default every readout and score uses the full vocabulary. J++ (Ayonrinde & "
               "Lindsey 2026) report theirs after Readout Filtering: every token whose text has no letter or digit "
               "(punctuation, whitespace, padding) is removed, the bank's target tokens spared. These switches read the "
               "same arms that way (evaluate.py writes both; <arm>/sem/). Judged scores are of the full readouts, so a "
               "semantic arm shows none.")
    all_sem = st.toggle("All arms: semantic tokens only", key="sem_all")
    st.toggle("J++ arms: semantic tokens only", key="sem_jpp", disabled=all_sem,
              help="Only the J++ arms (jpp:…) switch, so the J++ lens is read as its authors report it while the J-lens "
                   "arms stay on the full vocabulary." + (" On already: every arm is." if all_sem else ""))
    repo = sources.repo_state()
    st.caption(f"`{repo['branch']}` @ `{repo['sha']}`{' (dirty)' if repo['dirty'] else ''} · Qwen3.6-27B · "
               "J-lens n1000 `a4114d7` · numbers read from `out/` on load")
    hfsync.sidebar()

hfsync.start()  # background pull of the shared results (no-op without a configured dataset)

if (mode := sources.vocab_mode()) != "full":
    st.html('<div style="font-size:13px;color:var(--ink-2);margin:-6px 0 6px">Vocabulary view: <b>semantic tokens only</b> '
            f'for {"every arm" if mode == "all" else "the J++ arms"} (J++ Readout Filtering; arms not yet re-read keep '
            "the full vocabulary; judged scores are of the full readouts). Switch back in the sidebar.</div>")
nav.run()
