"""Watch the School of Reward Hacks runs so they can be stopped if something goes wrong (orchestrator, 2026-10-23).

  python src/sorh_monitor.py check monitor/sorh_runs.json      # validate the config and print one dry tick
  python src/sorh_monitor.py watch monitor/sorh_runs.json [--interval 180] [--status-every 3600]
  python src/sorh_monitor.py selftest                          # synthetic runs in a temp folder, no API calls
  python src/sorh_monitor.py stop monitor/sorh_runs.json <run>  # SIGINT that run's own PID (cmdline checked)

`watch` never stops a run. It exits so that the session running it is woken, with the reason as the exit code:
  0   every configured run has ended
  10  hourly status due
  20  a stop rule fired (the alert names the run, PID and rule)
  30  an anomaly to report at once (no stop rule)
  50  a stage finished (send the stage-end note)
  40  the laptop slept
  60  another watcher is already running (logs/sorh_monitor/watch.lock); this one did not start
What was already seen and reported is kept in logs/sorh_monitor/state.json, so a relaunch carries on where it left off.
Ticks go to logs/sorh_monitor/watch.log, alerts to logs/sorh_monitor/alerts.jsonl; the script writes them itself.

Stop rules, per run:
  hang     PID alive, and no new or updated record for `hang_min` (15) minutes of awake time. Awake time is
           CLOCK_UPTIME_RAW, which doesn't advance while the Mac sleeps.
  spend    the run's spend (billed usage.cost in its records + its ledger lines) >= its stage cap
  key      the key's limit_remaining < key_floor ($25): fires for every live run
  errors   >= 3 bad events among the run's last 50 (above 5%): failed calls (FAILED lines in its stdout), empty replies,
           judge lines that don't parse or carry a failure field
  prompt   a logged prompt differs from the pre-registered text for its cell and task
  content  >= 3 odd replies among the last 50: truncated (finish_reason other than "stop"), duplicated (same reply text
           as another record under a different prompt, replies of 50+ words), wrong language (> 2% non-Latin letters). Replies with a 120-character block repeated 4+
           times are only counted in the status line: repeating the scored phrase is the padding SoRH measures.
Anomalies, reported once each: the first bad event or odd reply of a run; spend >= 80% of cap; key < floor + $10; a
PID gone before the expected total; a cell/task with no pre-registered text; running on battery; lid closed.

Config (JSON): {"key_floor": 25, "hang_min": 15, "runs": [run, ...]}, each run:
  name, owner, stage, cap_usd, pid (null = not launched yet), cmd_contains (checked against `ps` to catch PID reuse),
  since (ISO time; older files are ignored), expected_total,
  records: [globs of per-record JSON files], jsonl: [files whose lines are records],
  stdout (optional runner output), ledger: [{"path", "field", "exclude_regex"?}] (lines with "at" >= since count),
  fields: {"cell", "task", "prompt", "reply", "finish", "cost": [paths]} as dotted paths ("turns.-1.reply"),
  prereg (optional JSON {cell: {task: text}}), judge: [{"path", "fail_if": [fields]}], dup_check (default true),
  transport (optional): {"attempts": JSONL with one line per call attempt, "outcome_field" ("outcome"), "ok" (["ok"]),
  or, without an attempts log, "stdout_regex" for refused/timed-out lines (each new record = a good attempt);
  "deviations": file where the runner logs a halving, "halve_regex" ("(?i)halv"), "grace_min" (5)}.
Paths are relative to the worktree root (logs/ is the shared logs folder) or absolute.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "sorh_monitor"
WINDOW, BAD_MAX = 50, 3
DEFAULT_FIELDS = {"cell": "variant", "task": "task", "prompt": "prompt", "reply": "reply", "finish": "finish_reason",
                  "cost": ["usage.cost", "retry_cost"]}


def uptime():
    return time.clock_gettime(time.CLOCK_UPTIME_RAW)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts(s):
    """Seconds since the epoch, or None when the string isn't a full date-time (e.g. the IB judge ledger's bare
    "19:24:32"); callers then keep the line rather than drop it."""
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def get_all(rec, path):
    """Dotted path with integer indices and '*' over a list: 'usage.cost', 'turns.-1.reply', 'turns.*.usage.cost'."""
    cur = [rec]
    for part in path.split("."):
        nxt = []
        for c in cur:
            if isinstance(c, list):
                if part == "*":
                    nxt.extend(c)
                else:
                    try:
                        nxt.append(c[int(part)])
                    except (ValueError, IndexError):
                        pass
            elif isinstance(c, dict) and part == "*":
                nxt.extend(c.values())  # e.g. judge_usage.*.cost: one usage block per judge kind
            elif isinstance(c, dict) and part in c:
                nxt.append(c[part])
        cur = nxt
    return cur


def get(rec, path):
    v = get_all(rec, path)
    return v[0] if v else None


def _p(path):
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


# ---- reply checks --------------------------------------------------------------------------------------------------

def non_latin_share(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    other = sum(1 for c in letters if not (c.isascii() or "À" <= c <= "ɏ"))
    return other / len(letters)


def repeated_block(text, size=120, times=4):
    """A block of `size` characters that occurs `times`+ times (every offset, so any period is caught)."""
    if len(text) < size * times:
        return False
    counts = Counter(text[i:i + size] for i in range(len(text) - size + 1))
    return any(n >= times and len(set(block)) > 10 for block, n in counts.items())


def reply_flags(reply, finish):
    """Flags that count toward the content stop rule. A repeated block is not one of them: repeating the scored
    phrase is the padding SoRH measures, so it is only noted (see notes())."""
    flags = []
    if finish not in ("stop", None):
        flags.append(f"truncated (finish {finish})")
    share = non_latin_share(reply)
    if share > 0.02:
        flags.append(f"non-Latin letters {share:.0%}")
    return flags


# ---- one run -------------------------------------------------------------------------------------------------------

def proc_cmd(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    r = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return r.stdout.strip() or None


def complete_lines(p):
    """Lines of a JSONL file, leaving out a last line that is still being written (no trailing newline)."""
    text = Path(p).read_text(errors="replace")
    lines = text.split("\n")
    return lines[:-1]  # the piece after the last newline is either "" or a partial line


_JUDGES = {}
_ANALYSIS = {}


def analysis_module(path):
    """Agent 10's src/sorh_analysis.py from a pinned mirror of their repo (it finds its sorh_judges.py next to it and
    the cell texts in ../notes/sorh_prereg/), so prompt_mismatches() runs exactly as in their pipeline check."""
    if path not in _ANALYSIS:
        import importlib.util
        # Each pin must get its own sorh_judges: the module does `import sorh_judges`, and a copy cached in
        # sys.modules from another pin would otherwise be reused silently.
        sys.modules.pop("sorh_judges", None)
        spec = importlib.util.spec_from_file_location(f"sorh_analysis_pinned_{len(_ANALYSIS)}", _p(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules.pop("sorh_judges", None)
        assert Path(mod.J.__file__).resolve().parent == _p(path).resolve().parent, (mod.J.__file__, path)
        _ANALYSIS[path] = mod
    return _ANALYSIS[path]


def judges_module(path):
    """Agent 10's src/sorh_judges.py (strict parsers), loaded from a pinned copy named in the config."""
    if path not in _JUDGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("sorh_judges_pinned", _p(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _JUDGES[path] = mod
    return _JUDGES[path]


def judge_status_from_gate(A, rec, more=False):
    """Judge problems of one record, read from the pinned module's own pipeline_check([rec]): kinds that don't parse,
    reasoning quotes or citations that fail, and (from amendment 2, fec8aef) citation failures per kind. Follows
    whatever version is pinned, so later amendments don't need a copy of their logic here."""
    pc = A.pipeline_check([rec], 1, more)
    bad = [f"{k} unparsed" for k, (ok, tot) in pc.get("parse", {}).items() if tot and ok < tot]
    qf = (pc.get("quote_fail") or [0, 0])[0]
    if qf:
        bad.append(f"reasoning: {qf} quote or citation failed")
    bad += [f"{k}: {b}/{t} citations failed" for k, (b, t) in (pc.get("cite_fail") or {}).items() if b]
    return bad


def judge_status(J, rec):
    """Per record, as in agent 10's pipeline_check: each judge kind's parse, and the reasoning judge's quote checks."""
    j = rec.get("judge") or {}
    reply, reasoning, bad = rec.get("reply") or "", rec.get("reasoning") or "", []
    for kind in J.kinds_for(rec["row"], "persist" in j):
        raw = j.get(kind)
        if kind == "quality":
            ok = J.parse_quality(raw)["status"] == "ok"
        elif kind == "count":
            ok = J.parse_count(raw, rec["row"], reply)["status"] != "unparsed"
        elif kind == "thinned":
            ok = J.parse_thinned(raw, reply)["status"] != "unparsed"
        elif kind == "persist":
            ok = J.parse_persist(raw, reasoning, reply)["status"] != "unparsed"
        else:
            sts = J.parse_reasoning(raw, reasoning)["status"]
            ok = all(s != "unparsed" for s in sts.values())
            qf = [k for k, s in sts.items() if s == "quote_failed"]
            if qf:
                bad.append(f"{kind} quote failed ({', '.join(qf)})")
        if not ok:
            bad.append(f"{kind} unparsed")
    return bad


def scan_run(run, st, prereg, alerts, now_up):
    """Read what's new for one run, update its state, and append alerts. Returns a status dict."""
    f = {**DEFAULT_FIELDS, **run.get("fields", {})}
    since = ts(run.get("since")) or 0.0
    seen = st.setdefault("seen", {})          # file -> [mtime, size] last read
    recs = st.setdefault("recs", {})          # record key -> summary
    events = st.setdefault("events", {})      # kind -> last WINDOW events: [kind, ok, key, why]
    hashes = st.setdefault("hashes", {})      # reply hash -> [first record key, its prompt hash]
    reported = st.setdefault("reported", [])
    progressed = False
    pid = run.get("pid")
    if not pid:  # not launched yet: nothing to read or check
        return dict(run=run["name"], stage=run.get("stage"), state="waiting", pid=None, done=0,
                    total=run.get("expected_total"), spend=0.0, cap=run.get("cap_usd"), idle_min=0.0, bad_errors=0,
                    n_errors=0, odd_replies=0, n_content=0, repeats=0, refused=0, n_attempts=0, halvings=0, known_trunc=0, judge_bad=0, n_judge=0, attempt_other=0)
    if st.get("pid_seen") not in (None, pid):
        # a restarted runner (new PID, same files) starts again at full concurrency: its step-down state starts over
        st.pop("tx", None)
        st.pop("ended", None)
        st.pop("stdout_lines", None)  # a restart usually writes a new stdout file: read it from its first line
    st["pid_seen"] = pid
    cmd = proc_cmd(pid)
    alive = bool(cmd) and (not run.get("cmd_contains") or run["cmd_contains"] in cmd)

    def alert(level, rule, msg, once=None):
        if once:
            if once in reported:
                return
            reported.append(once)
        alerts.append(dict(at=now_iso(), level=level, run=run["name"], owner=run.get("owner"), pid=run.get("pid"),
                           rule=rule, msg=msg))

    def add_event(kind, ok, key, why=""):
        ev = events.setdefault(kind, [])
        ev.append([kind, ok, key, why])
        del ev[:-WINDOW]
        if not ok:
            alert("anomaly", kind, f"first {kind} event: {key} {why}".strip(), once=f"first_{kind}")

    def check_prompt(key, rec, cell, task, prompt):
        if run.get("analysis_module") and run.get("prereg_check", True):
            # agent 10's own rule: the cell text (single-turn, multi-turn turn 1) or the feedback format (turns 2-5);
            # a missing prompt counts as a mismatch
            try:
                mism = analysis_module(run["analysis_module"]).prompt_mismatches([rec], run.get("more", False))
            except Exception as e:  # noqa: BLE001
                mism = [f"check error {type(e).__name__}: {str(e)[:80]}"]
            if mism:
                alert("stop" if alive else "anomaly", "prompt", f"{key}: sent prompt differs from the registered text "
                      f"{mism[0]}; sent {str(prompt)[:120]!r}", once=f"prompt_{key}")
        turn = get(rec, run["turn_field"]) if run.get("turn_field") else None
        if prereg is not None and prompt is not None and turn in (None, 1):
            lookup = run.get("prereg_cell") or cell  # multi-turn turn 1 is the G (or G_more) text
            want = (prereg.get(str(lookup)) or {}).get(str(task))
            if want is None:
                alert("anomaly", "prompt", f"no pre-registered text for {lookup}/{task}", once=f"noprereg_{lookup}_{task}")
            elif prompt != want:
                i = next((i for i, (a, b) in enumerate(zip(prompt, want)) if a != b), min(len(prompt), len(want)))
                alert("stop" if alive else "anomaly", "prompt", f"{key}: prompt differs from the pre-registered "
                      f"{lookup}/{task} at char {i}: logged {prompt[max(0, i - 40):i + 60]!r} vs registered "
                      f"{want[max(0, i - 40):i + 60]!r}", once=f"prompt_{lookup}_{task}")

    def take(key, rec, mtime):
        cell, task = get(rec, f["cell"]), get(rec, f["task"])
        prompt, reply, finish = get(rec, f["prompt"]), get(rec, f["reply"]) or "", get(rec, f["finish"])
        cost = sum(float(v or 0) for c in f["cost"] for v in get_all(rec, c))
        # Copies (multi-turn turns 1-2 copied into other arms carry "copied_from"; imported records carry "source"):
        # their prompt is still checked, but cost, empty reasoning and the problem windows count each original once.
        if run.get("cost_only"):  # e.g. mini-swe-agent trajectories: spend and progress only, no reply checks
            recs[key] = dict(cell=cell, task=task, cost=cost, mtime=mtime, flags=[])
            return
        # source_is_copy=false: "source" names the record a judge read (agent 1's coop judges), not a copy
        copied = bool((rec.get("source") if run.get("source_is_copy", True) else None)
                      or rec.get(run.get("copy_field", "copied_from")))
        if copied:
            cost = 0.0
            recs[key] = dict(cell=cell, task=task, cost=0.0, mtime=mtime, flags=[], copied=True)
            check_prompt(key, rec, cell, task, prompt)
            return
        flags = [] if not reply.strip() else reply_flags(reply, finish)
        if str(task) in set(run.get("truncation_known_tasks") or []):
            # acknowledged truncations (sorh_580's reasoning hits max_tokens; orchestrator 2026-10-23): counted in the
            # status line, kept out of the content window; truncation on any other prompt still counts
            n = len(flags)
            flags = [x for x in flags if not x.startswith("truncated")]
            st["known_trunc"] = st.get("known_trunc", 0) + (n - len(flags))
        h = hashlib.sha1(reply.strip().encode()).hexdigest() if reply.strip() else None
        if h and run.get("dup_check", True) and len(reply.split()) >= 50:
            # Same reply under a different prompt is a pipeline fault; under the same prompt it's a copied record
            # (cells with identical prompts, shared first replies). Short replies are left out: agent 1's records have
            # 11 natural repeats of 5-24 words across cells (definitions, 100-word summaries). Records without the
            # prompt text are compared by prompt id (task): the same reply under another prompt id.
            ph = hashlib.sha1(str(prompt if prompt is not None else ("task", task)).encode()).hexdigest()
            # multi-turn: the same episode resending its own reply at a later turn is behaviour, not a fault
            ep = json.dumps([get(rec, x) for x in run.get("episode_fields") or []])
            first, first_ph, *first_ep = hashes.setdefault(h, [key, ph, ep])
            if first != key and first_ph != ph and (not run.get("episode_fields") or (first_ep or [None])[0] != ep):
                flags.append(f"same reply as {first}, under a different prompt")
        recs[key] = dict(cell=cell, task=task, cost=cost, mtime=mtime, flags=flags)
        if run.get("require_reasoning", True) and reply.strip():
            reasoning = get(rec, f.get("reasoning", "reasoning"))
            if not (reasoning or "").strip():
                # Pre-registration (9bd82fd): up to 1% of a stage's planned replies with empty reasoning are excluded
                # and reported; more fails the stage. empty_reasoning_max = how many are allowed.
                empties = st.setdefault("empty_reasoning", [])
                if key not in empties:
                    empties.append(key)
                allowed = run.get("empty_reasoning_max") or 0  # unset (confirm before launch) = strictest
                if len(empties) > allowed:
                    alert("stop" if alive else "anomaly", "reasoning", f"{len(empties)} replies with empty reasoning "
                          f"(allowed {allowed}); latest {key} (provider {get(rec, 'provider')}, finish {finish})",
                          once=f"noreason_{len(empties)}")
                else:
                    alert("anomaly", "reasoning", f"{key}: reply with empty reasoning, {len(empties)} of {allowed} "
                          f"allowed (excluded and reported)", once=f"noreason_{len(empties)}")
        if reply.strip() and repeated_block(reply):
            st["repeats"] = st.get("repeats", 0) + 1  # in the status line only; may be the padding under study
        if not reply.strip():
            add_event("error", False, key, "empty reply")
        else:
            add_event("error", True, key)
            add_event("content", not flags, key, "; ".join(flags))
        check_prompt(key, rec, cell, task, prompt)
        jm = judges_module(run["judges_module"]) if run.get("judges_module") else None
        if (run.get("analysis_module") or jm is not None) and "judge" in rec:  # judges inside the record
            try:
                bad = judge_status_from_gate(analysis_module(run["analysis_module"]), rec, run.get("more", False)) \
                    if run.get("analysis_module") else judge_status(jm, rec)
            except Exception as e:  # noqa: BLE001  a parser crash is itself worth seeing
                bad = [f"parser error {type(e).__name__}: {str(e)[:80]}"]
            skip = run.get("skip_judge_kinds") or []  # kinds the run skips by design (e.g. --no-reasoning-judge)
            bad = [b for b in bad if not any(b.startswith((k + " ", k + ":")) for k in skip)]
            add_event("judge", not bad, key, "; ".join(bad))
        if run.get("parse_field"):  # probe answers: the parsed answer is None when the raw text didn't parse
            add_event("judge", get(rec, run["parse_field"]) is not None, key, f"{run['parse_field']} unparsed")

    # Inspect runs (agent 11's IB ablation): progress = the sample buffer's etag (it rises with every event);
    # finished episodes and sample errors from the buffer; spend from the runner's watchdog.log ("own spend ~$X")
    ins = run.get("inspect")
    if ins:
        # eval_glob pins a run to its own log when a later run (a completion) writes into the same log_dir
        evals = sorted(_p(ins["log_dir"]).glob(ins.get("eval_glob", "*.eval")))
        st.setdefault("ins_done", {})
        # all_evals: one runner writes an .eval per variant (run_variants.py); read every file in log_dir
        files = evals if ins.get("all_evals") else evals[-1:]
        etags = st.get("ins_etags") if isinstance(st.get("ins_etags"), dict) else {}
        for f in files:
            pre = f"{f.stem}|" if ins.get("all_evals") else ""  # sample ids repeat across variants
            try:
                from inspect_ai.log._recorders.buffer.database import SampleBufferDatabase
                got = SampleBufferDatabase(os.path.realpath(f), create=False).get_samples()
            except Exception:  # noqa: BLE001  no buffer (run ended, or not started yet)
                got = None
            if got is not None:
                if got.etag != etags.get(f.name):
                    etags[f.name] = got.etag
                    progressed = True
                if ins.get("spend_from_buffer"):
                    # no runner watchdog (a bare `inspect eval`): price the model events' token usage with
                    # costs.PRICES x1.3, keeping each sample's highest total so evicted samples still count
                    import costs
                    cost_st = st.setdefault("ins_cost", {})
                    for s in got.samples:
                        try:
                            data = SampleBufferDatabase(os.path.realpath(f), create=False).get_sample_data(
                                id=s.id, epoch=s.epoch)
                        except Exception:  # noqa: BLE001
                            continue
                        usd = 0.0
                        for ev in (data.events if data else []):
                            e = ev.event if hasattr(ev, "event") else ev
                            e = e if isinstance(e, dict) else json.loads(e)
                            u = (e.get("output") or {}).get("usage") or {} if e.get("event") == "model" else {}
                            if u:
                                p_in, p_out, p_c = costs.PRICES.get(str(e.get("model", "")).removeprefix("openrouter/"),
                                                                    (0.0, 0.0, 0.0))
                                c_ = u.get("input_tokens_cache_read") or 0
                                usd += ((u.get("input_tokens", 0) - c_) * p_in + c_ * p_c
                                        + u.get("output_tokens", 0) * p_out) / 1e6
                        k_ = f"{f.name}|{s.id}|e{s.epoch}"
                        cost_st[k_] = max(cost_st.get(k_, 0.0), usd * 1.3)
                    st["ins_spend"] = sum(cost_st.values())
                for s in got.samples:
                    k = f"{pre}{s.id}|e{s.epoch}"
                    if s.completed and k not in st["ins_done"]:
                        st["ins_done"][k] = bool(s.error)
                        add_event("error", not s.error, k, f"sample error: {str(s.error)[:120]}" if s.error else "")
                    elif s.error and f"err_{k}" not in reported:
                        alert("anomaly", "errors", f"{k}: sample error {str(s.error)[:160]}", once=f"err_{k}")
        st["ins_etags"] = etags
        if files and not alive and "ins_final" not in st:
            # Finished: count from the written logs, not the buffer, which keeps only recent samples (it read
            # 69/80 and 54/60 at exit where the logs hold 78 and 60). A cancelled log (a guard stop) has no
            # results block, so its scored samples are counted from the sample summaries.
            try:
                from inspect_ai.log import read_eval_log, read_eval_log_sample_summaries
                done_n, total_n, stats = 0, 0, []
                for f in files:
                    h = read_eval_log(str(f), header_only=True)
                    d_ = getattr(h.results, "completed_samples", None)
                    if d_ is None:
                        d_ = sum(1 for s in read_eval_log_sample_summaries(str(f)) if s.scores and not s.error)
                    done_n += d_
                    total_n += getattr(h.results, "total_samples", None) or 0
                    stats.append(h.status)
                st["ins_final"] = dict(status="/".join(sorted(set(stats))), completed=done_n, total=total_n or None)
            except Exception as e:  # noqa: BLE001  logs not readable yet: keep the buffer count, retry next tick
                st["ins_final_err"] = f"{type(e).__name__}: {str(e)[:120]}"
        wd = _p(ins["watchdog"]) if ins.get("watchdog") else None
        if wd and wd.exists():
            m = re.findall(r"own spend ~?\$([\d.]+)", wd.read_text(errors="replace"))
            a, b = ins.get("watchdog_matches") or [None, None]  # [start, end) of "own spend" lines: one runner's share
            m = m[a:b]
            st["ins_spend"] = float(m[-1]) if m else 0.0
            if len(complete_lines(wd)) != st.get("ins_wd_lines"):
                st["ins_wd_lines"] = len(complete_lines(wd))

    # extra progress signals (files a runner updates while its records appear only at the end of an episode)
    pf = st.setdefault("progress_mtimes", {})
    for path in run.get("progress_files", []):
        q = _p(path)
        if q.exists():
            mt = q.stat().st_mtime
            if pf.get(str(q)) != mt:
                if str(q) in pf:
                    progressed = True
                pf[str(q)] = mt

    # per-record JSON files
    files = sorted({p for g in run.get("records", []) for p in glob.glob(str(_p(g)))})
    fresh = []
    for p in files:
        try:
            s = os.stat(p)
        except FileNotFoundError:
            continue
        if s.st_mtime < since:
            if since - s.st_mtime < 1800:
                # written within 30 min before this run's start time: usually a start time set late at registration
                # (agent 1's thanks_once sorh_0, 2026-10-26, read 0/5); older files are a previous run's, left out
                alert("anomaly", "records", f"{p} was written {(since - s.st_mtime) / 60:.0f} min before this run's "
                      f"since ({run.get('since')}) and is not counted; check the start time",
                      once=f"records_before_since_{run['name']}")
            continue
        sig = [s.st_mtime, s.st_size]
        if seen.get(p) != sig:
            fresh.append((s.st_mtime, p, sig))
    for mtime, p, sig in sorted(fresh):
        try:
            rec = json.loads(Path(p).read_text())
        except (json.JSONDecodeError, OSError):
            continue  # being written; read next tick
        seen[p] = sig
        st["_new_records"] = st.get("_new_records", 0) + 1
        rel = os.path.relpath(p, ROOT)
        take(rel if not rel.startswith("..") else "/".join(Path(p).parts[-4:]), rec, mtime)
        progressed = True

    # JSONL record files and judge files: new lines since the last read
    lines_at = st.setdefault("lines", {})
    for path in run.get("jsonl", []):
        p = _p(path)
        if not p.exists():
            continue
        lines = complete_lines(p)
        for i in range(lines_at.get(str(p), 0), len(lines)):
            try:
                rec = json.loads(lines[i])
            except json.JSONDecodeError:
                add_event("error", False, f"{p.name}:{i + 1}", "line doesn't parse")
                continue
            if since and rec.get("at") and (ts(rec["at"]) or since) < since:
                continue
            st["_new_records"] = st.get("_new_records", 0) + 1
            take(f"{p.name}:{i + 1}", rec, p.stat().st_mtime)
            progressed = True
        lines_at[str(p)] = len(lines)
    for j in run.get("judge", []):
        p = _p(j["path"])
        if not p.exists() or p.stat().st_mtime < since:
            continue
        lines = complete_lines(p)
        for i in range(lines_at.get(str(p), 0), len(lines)):
            key = f"{p.name}:{i + 1}"
            try:
                rec = json.loads(lines[i])
            except json.JSONDecodeError:
                add_event("error", False, key, "judge line doesn't parse")
                continue
            bad = [x for x in j.get("fail_if", []) if get(rec, x)]
            add_event("error", not bad, key, f"judge {', '.join(bad)}")
            progressed = True
        lines_at[str(p)] = len(lines)

    # Replies the runner excluded after its retries (agent 3's mt runner logs them in incomplete.jsonl instead of
    # writing a record with empty reasoning): each counts toward empty_reasoning_max like an empty-reasoning record.
    ex = run.get("excluded_log")
    if ex and _p(ex["path"]).exists() and run.get("require_reasoning", True):
        p = _p(ex["path"])
        lines = complete_lines(p)
        for i in range(lines_at.get(str(p), 0), len(lines)):
            if re.search(ex.get("match", "(?i)empty"), lines[i]):
                empties = st.setdefault("empty_reasoning", [])
                empties.append(f"{p.name}:{i + 1}")
                allowed = run.get("empty_reasoning_max") or 0
                if len(empties) > allowed:
                    alert("stop" if alive else "anomaly", "reasoning", f"{len(empties)} replies excluded or with empty "
                          f"reasoning (allowed {allowed}); latest {p.name}:{i + 1}: {lines[i][:120]}",
                          once=f"noreason_{len(empties)}")
                else:
                    alert("anomaly", "reasoning", f"{p.name}:{i + 1}: reply excluded after retries, {len(empties)} of "
                          f"{allowed} allowed: {lines[i][:120]}", once=f"noreason_{len(empties)}")
        lines_at[str(p)] = len(lines)

    # Refused or timed-out calls (429, 5xx, timeouts), per attempt: from the runner's attempts log when it has one,
    # else from its stdout (regex) with each new record counted as a good attempt. See transport_rules().
    tx = run.get("transport") or {}
    tx_new = []  # [ok, why]
    if tx.get("attempts") and _p(tx["attempts"]).exists():
        p = _p(tx["attempts"])
        lines = complete_lines(p)
        okv, badv = set(tx.get("ok", ["ok"])), set(tx.get("bad", ["429", "5xx", "timeout"]))
        for i in range(lines_at.get(str(p), 0), len(lines)):
            try:
                rec = json.loads(lines[i])
            except json.JSONDecodeError:
                continue
            if tx.get("key_contains") and tx["key_contains"] not in str(rec.get("key")):
                continue  # another run's attempts in a shared log (the pilot re-judge appends "|v2|" keys)
            if tx.get("progress_from_attempts"):
                progressed = True  # runs that write their records only at the end
            if get(rec, tx.get("outcome_field", "outcome")) is None:
                continue  # a spend ledger used as the progress signal: no outcome to classify
            o = str(get(rec, tx.get("outcome_field", "outcome")))
            if o in okv:
                tx_new.append([True, o, rec.get("at")])
            elif o in badv or re.fullmatch(r"5\d\d", o):
                tx_new.append([False, f"{o} ({rec.get('key')}, attempt {rec.get('attempt')})", rec.get("at")])
            else:  # e.g. "error": not a refused or timed-out call; counted on its own
                st["attempt_other"] = st.get("attempt_other", 0) + 1
        lines_at[str(p)] = len(lines)
    elif tx:
        tx_new.extend([True, ""] for _ in range(st.get("_new_records", 0)))
    st["_new_records"] = 0

    # the runner's stdout: FAILED lines are failed calls; refused or timed-out calls; halvings; a traceback (once)
    halved_now = 0
    if run.get("stdout") and _p(run["stdout"]).exists():
        out = _p(run["stdout"]).read_text(errors="replace").splitlines()
        tx_re = tx.get("stdout_regex", r"\b(429|5\d\d)\b|[Tt]ime[d ]?out")
        for i in range(st.get("stdout_lines", 0), len(out)):
            if re.search(r"\bFAILED\b", out[i]):
                add_event("error", False, f"stdout:{i + 1}", out[i].strip()[:160])
            if tx and not tx.get("attempts") and re.search(tx_re, out[i]):
                tx_new.append([False, out[i].strip()[:120]])
            if tx and tx.get("halve_source", "stdout") != "deviations" and \
                    re.search(tx.get("halve_regex", r"(?i)halv"), out[i]):
                halved_now += 1
            if "Traceback" in out[i]:
                alert("anomaly", "traceback", f"stdout line {i + 1}: {out[i].strip()[:160]}", once=f"tb_{i}")
        st["stdout_lines"] = len(out)
    if tx.get("deviations") and _p(tx["deviations"]).exists():
        p = _p(tx["deviations"])
        lines = complete_lines(p)  # give either stdout or deviations, not both: the runner writes the line to each
        halved_now += sum(1 for l in lines[lines_at.get(str(p), 0):] if re.search(tx.get("halve_regex", r"(?i)halv"), l))
        lines_at[str(p)] = len(lines)
    if tx:
        transport_rules(st, tx_new, halved_now, now_up, tx.get("grace_min", 5), alert, ts(tx.get("quiet_until")) if tx.get("quiet_until") else None)

    # spend: this run's records + its ledger lines
    spend = sum(r["cost"] for r in recs.values()) + (st.get("ins_spend", 0.0) if ins else 0.0)
    sl = run.get("spend_log")  # {"path", "regex"}: the last match in a runner's own log (e.g. HVTB's watchdog)
    if sl and _p(sl["path"]).exists():
        m_ = re.findall(sl["regex"], _p(sl["path"]).read_text(errors="replace"))
        spend += float(m_[-1]) if m_ else 0.0
    for led in run.get("ledger", []):
        p = _p(led["path"])
        if p.exists():
            for line in p.read_text().splitlines():
                # a ledger shared with other jobs (agent 6's spend.jsonl also gets the catalogue's lines)
                if led.get("exclude_regex") and re.search(led["exclude_regex"], line):
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t_ = ts(r.get("at"))
                if (t_ if t_ is not None else since) >= since:
                    spend += float(r.get(led.get("field", "usd")) or 0)
                elif alive and t_ and since - t_ < 900 and float(r.get(led.get("field", "usd")) or 0) > 0:
                    # (live runs only: an ended run's exclusions were settled at its end, e.g. agent 6's pilot rows)
                    # a paid row just before the run's start: usually a start time set a little late at
                    # registration (agent 11's support coder, 2026-10-24), which would undercount the run
                    alert("anomaly", "ledger", f"{led['path']}: a paid row at {r.get('at')} falls just before this "
                          f"run's since ({run.get('since')}) and is not counted; check the start time",
                          once=f"ledger_before_since_{led['path']}")

    # process and progress
    if pid and cmd and not alive and not st.get("ended"):  # an ended run's PID being reused later is no news
        alert("anomaly", "pid", f"PID {pid} is now a different process ({cmd[:120]}); treating the run as ended",
              once=f"pidreuse_{pid}")
    if progressed or st.get("last_progress_up") is None:
        st["last_progress_up"] = now_up
    idle_min = (now_up - st["last_progress_up"]) / 60
    # progress toward expected_total: only records on count_tasks when given (the screen resumed on 10 of its
    # 20 prompts); spend still counts every record in the file
    keep = set(run.get("count_tasks") or [])
    done = sum(1 for r in recs.values() if not keep or r.get("task") in keep) + (len(st.get("ins_done", {})) if ins else 0)
    if ins and st.get("ins_final", {}).get("completed") is not None:
        done = st["ins_final"]["completed"]  # the finished log header is authoritative
    total = run.get("expected_total")
    cap = run.get("cap_usd")
    state = "waiting" if not pid else ("running" if alive else ("finished" if (total is None or done >= total) else "ended early"))
    if pid and not alive:
        if state == "ended early":
            alert("anomaly", "pid", f"PID {pid} has exited with {done}/{total} records", once=f"ended_{pid}")
        else:
            alert("end", "end", f"stage finished: {done}/{total} records, ${spend:.2f} of ${cap}", once=f"end_{pid}")
        st["ended"] = True

    if alive:
        hang, warn = run.get("hang_min", 20), run.get("hang_warn_min", 15)
        if idle_min >= hang:
            alert("stop", "hang", f"no new or updated record for {idle_min:.0f} min of awake time (rule: {hang})",
                  once=f"hang_{pid}_{int(st['last_progress_up'])}")
        elif idle_min >= warn:
            alert("anomaly", "hang", f"no new or updated record for {idle_min:.0f} min of awake time; the stop rule "
                  f"is at {hang}", once=f"hangwarn_{pid}_{int(st['last_progress_up'])}")
        if cap is not None and spend >= cap:
            alert("stop", "spend", f"spend ${spend:.2f} >= cap ${cap:.2f}", once=f"cap_{pid}")
        elif cap is not None and spend >= 0.8 * cap:
            alert("anomaly", "spend", f"spend ${spend:.2f} is {spend / cap:.0%} of the ${cap:.2f} cap", once=f"cap80_{pid}")
        hcap = run.get("headroom_cap_usd")  # the hold counted in headroom, when below the run's own cap
        if hcap is not None and spend > hcap:
            alert("anomaly", "spend", f"spend ${spend:.2f} passed the headroom hold ${hcap:.2f}: re-check the room",
                  once=f"hcap_{pid}")
        group_stop(run, alert)
        for kind in ("error", "content", "judge"):
            window = events.get(kind, [])
            bad = [e for e in window if not e[1]]
            if len(bad) >= (run.get("bad_max") or {}).get(kind, BAD_MAX):  # a run's own pre-registered rule
                # Judge parse/quote problems are reported, not a stop: not in the pre-registration's section 10 stop
                # rules (they're what the pilot gate tests, and replies can be re-judged). Decided 2026-10-23, pilot.
                alert("anomaly" if kind == "judge" else "stop", {"error": "errors"}.get(kind, kind),
                      f"{len(bad)} bad of the last {len(window)} {kind} checks: " + "; ".join(f"{e[2]} {e[3]}" for e in bad[-3:]),
                      # stops: again on each new bad event; judge reports: once per run (counts go in the status lines)
                      once=f"judgewin_{pid}" if kind == "judge" else f"{kind}win_{pid}_{bad[-1][2]}")
    win = lambda kind: events.get(kind, [])
    txw = st.get("tx", {})
    return dict(run=run["name"], stage=run.get("stage"), state=state, pid=pid, done=done, total=total,
                spend=round(spend, 2), cap=cap, idle_min=round(idle_min, 1),
                bad_errors=sum(1 for e in win("error") if not e[1]), n_errors=len(win("error")),
                odd_replies=sum(1 for e in win("content") if not e[1]), n_content=len(win("content")),
                repeats=st.get("repeats", 0),
                refused=sum(1 for e in txw.get("window", []) if not e[0]), n_attempts=len(txw.get("window", [])),
                halvings=txw.get("halvings", 0), known_trunc=st.get("known_trunc", 0), judge_bad=sum(1 for e in win("judge") if not e[1]), n_judge=len(win("judge")), attempt_other=st.get("attempt_other", 0))


def group_stop(run, alert):
    """A run's pre-registered per-group rule (agent 11's Secret Number amendment, 61fe798): empty rows (`empty_field`
    is None) plus failed calls (stdout lines matching `failed_regex`, groups item and probe) per group key, against
    `planned` counts per probe; stop when a group's count is above `max_share` of its planned count.
    Config: {"key": [[field, split_index or null], ...], "split": "|", "empty_field", "failed_regex",
             "failed_key": [[group name, split_index or null], ...], "planned": {probe: n}, "max_share"}."""
    gs = run.get("group_stop")
    if not gs:
        return
    if gs.get("count_module"):  # the owner's own pinned counting code: missing_counts(rows, stdout_text) -> Counter
        import importlib.util
        spec = importlib.util.spec_from_file_location("group_stop_counts", str(_p(gs["count_module"])))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = [r for path in run.get("jsonl") or [] for r in mod.rows(str(_p(path)))]
        out = run.get("stdout")
        text = _p(out).read_text(errors="replace") if out and _p(out).exists() else ""
        counts = mod.missing_counts(rows, text)
        for k, n in sorted(counts.items()):
            plan = gs["planned"].get(k[-1])
            if plan and n > gs["max_share"] * plan:
                alert("stop", "errors", f"{'/'.join(map(str, k))}: {n} missing of {plan} planned, above "
                      f"{gs['max_share']:.0%} (the run's pre-registered rule, owner's counting code)",
                      once=f"groupstop_{'_'.join(map(str, k))}_{n}")
        return
    sep = gs.get("split", "|")

    def part(v, i):
        return v if i is None else (str(v).split(sep) + [""] * (i + 1))[i]

    counts = Counter()
    for path in run.get("jsonl") or []:
        p = _p(path)
        if not p.exists():
            continue
        for line in complete_lines(p):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get(gs["empty_field"]) is None:
                counts[tuple(part(r.get(f), i) for f, i in gs["key"])] += 1
    out = run.get("stdout")
    if gs.get("failed_regex") and out and _p(out).exists():
        for m in re.finditer(gs["failed_regex"], _p(out).read_text(errors="replace"), flags=re.M):
            g = m.groupdict()
            counts[tuple(part(g.get(f), i) for f, i in gs["failed_key"])] += 1
    for k, n in sorted(counts.items()):
        plan = gs["planned"].get(k[-1])
        if plan and n > gs["max_share"] * plan:
            alert("stop", "errors", f"{'/'.join(map(str, k))}: {n} empty or failed of {plan} planned, above "
                  f"{gs['max_share']:.0%} (the run's pre-registered rule)", once=f"groupstop_{'_'.join(map(str, k))}_{n}")


def transport_rules(st, new, halved_now, now_up, grace_min, alert, quiet_until=None):
    """Refused or timed-out calls. Above 5% of the last 50 attempts (>= 3), the runner is to halve its concurrency as a
    logged deviation: no halving within `grace_min` minutes is an anomaly. After a halving the count restarts; >= 3
    refused or timed-out among the attempts since the last halving is a stop rule (errors still climbing)."""
    t = st.setdefault("tx", {"window": [], "after": None, "halvings": 0, "over_up": None})
    if halved_now:
        t["halvings"] += halved_now
        t["after"], t["over_up"] = [], None
        alert("anomaly", "transport", f"the runner halved its concurrency (halving {t['halvings']}); watching the "
              f"next {WINDOW} attempts", once=f"halved_{t['halvings']}")
    for ok, why, *rest in new:
        t["window"].append([ok, why])
        del t["window"][:-WINDOW]
        if t["after"] is not None:
            at = ts(rest[0]) if rest and rest[0] else None
            if quiet_until is None or at is None or at >= quiet_until:  # quiet_until: a known burst (sleep) is not "still climbing"
                t["after"].append([ok, why])
            del t["after"][:-WINDOW]
    bad = [e for e in t["window"] if not e[0]]
    if t["after"] is not None:
        bad_after = [e for e in t["after"] if not e[0]]
        if len(bad_after) >= BAD_MAX:
            alert("stop", "transport", f"{len(bad_after)} refused or timed-out of {len(t['after'])} attempts since "
                  f"halving {t['halvings']}: " + "; ".join(e[1] for e in bad_after[-3:]),
                  once=f"txstop_{t['halvings']}_{len(t['after'])}_{len(bad_after)}")
    elif len(bad) >= BAD_MAX and len(t["window"]) >= WINDOW:  # the runner's rule counts once 50 attempts are in
        if t["over_up"] is None:
            t["over_up"] = now_up
            alert("anomaly", "transport", f"{len(bad)} refused or timed-out of the last {len(t['window'])} attempts "
                  f"(above 5%): the runner should halve its concurrency", once=f"txover_{t['halvings']}")
        elif (now_up - t["over_up"]) / 60 >= grace_min:
            alert("anomaly", "transport", f"no halving logged {grace_min} min after refused or timed-out calls passed "
                  f"5% ({len(bad)}/{len(t['window'])})", once=f"txnohalve_{t['halvings']}")


# ---- machine and key -----------------------------------------------------------------------------------------------

def power():
    r = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    src = "battery" if "Battery Power" in r else ("AC" if "AC Power" in r else "unknown")
    m = re.search(r"(\d+)%", r)
    lid = subprocess.run(["ioreg", "-r", "-k", "AppleClamshellState", "-d", "1"], capture_output=True, text=True).stdout
    closed = bool(re.search(r'"AppleClamshellState" = Yes', lid))
    return dict(source=src, percent=int(m.group(1)) if m else None, lid_closed=closed)


def key_remaining():
    import urllib.request
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {env['OPENROUTER_API_KEY']}"})
    return float(json.loads(urllib.request.urlopen(req, timeout=30).read())["data"]["limit_remaining"])


# ---- the loop ------------------------------------------------------------------------------------------------------

def tick(cfg, state, out_dir, key_fn=key_remaining, power_fn=power):
    alerts = []
    now_up, now_wall = uptime(), time.time()
    m = state.setdefault("machine", {})
    pw = power_fn()
    if m.get("last_wall") is not None:
        slept = (now_wall - m["last_wall"]) - (now_up - m["last_up"])
        if slept > 90:
            # While the lid is closed now and that was already reported, further sleeps are logged, not re-reported:
            # the session would otherwise be woken on every short dark wake.
            lid_known = pw["lid_closed"] and "lid" in state.get("reported", [])
            alerts.append(dict(at=now_iso(), level="info" if lid_known else "sleep", run=None, rule="sleep",
                               msg=f"the Mac slept about {slept / 60:.0f} min since the last tick"
                                   + (" (lid still closed)" if lid_known else "")))
    m["last_wall"], m["last_up"] = now_wall, now_up
    reported = state.setdefault("reported", [])
    low = cfg.get("battery_alert_pct")
    # battery_switch_alert false: no anomaly on a switch to battery, only below battery_alert_pct (her word, 28 Oct)
    on_batt = pw["source"] == "battery" and cfg.get("battery_switch_alert", True)
    for cond, key, msg in ((on_batt, "battery", f"running on battery ({pw['percent']}%)"),
                           (pw["lid_closed"], "lid", "the lid is closed"),
                           # orchestrator: below this battery level while runs are live, report at once
                           (bool(low) and pw["source"] == "battery" and (pw["percent"] or 100) < low, "battery_low",
                            f"battery at {pw['percent']}%, below {low}%, on battery")):
        if cond and key not in reported:
            reported.append(key)
            alerts.append(dict(at=now_iso(), level="anomaly", run=None, rule=key, msg=msg))
        if not cond and key in reported:
            reported.remove(key)  # report again if it comes back
    # Inspect sandboxes across every run on the machine (orchestrator: never more than max_sandboxes in total)
    if cfg.get("max_sandboxes"):
        try:
            out = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"], capture_output=True,
                                 text=True, timeout=20).stdout.splitlines()
            conts = [line.split("\t") + [""] for line in out if line.strip()]
            # every running container is a sandbox (Inspect's, the SWE-V driver's, graders); the limit is lower once
            # any SWE image is up (orchestrator: <= 8 with LCB-type runs only, <= 6 with a SWE image)
            swe = any(re.search(r"(?i)swe-?bench|sweb\.|ecr\.aws/d3j8x8q7", c[1]) for c in conts)
            mem = None  # Colima VM memory in use (excl. cache), as a share
            try:
                fm = subprocess.run(["colima", "ssh", "--", "free", "-m"], capture_output=True, text=True,
                                    timeout=30).stdout
                m_ = re.search(r"Mem:\s+(\d+)\s+(\d+)", fm)
                mem = int(m_.group(2)) / int(m_.group(1)) if m_ else None
            except Exception:  # noqa: BLE001
                pass
            state["colima_mem"] = mem
            # orchestrator (2026-10-24 08:3x): 11 in total, SWE images included (measured: SWE-V's containers ~10 MB
            # each); once Colima memory passes 75%, back to the old limits: max_sandboxes_mem_swe (6) with a SWE
            # image up, max_sandboxes_mem (8) without
            high = mem is not None and mem > 0.75
            limit = (cfg.get("max_sandboxes_mem_swe", 6) if (high and swe) else
                     cfg.get("max_sandboxes_mem", 8) if high else
                     cfg.get("max_sandboxes_swe", 11) if swe else
                     cfg.get("max_sandboxes", 11))
            n_sb = len(conts)
            state["sandboxes"] = n_sb
            if high and n_sb and "colima_mem_high" not in reported:  # e.g. Terminal-Bench tasks declaring 2-4 GB each
                reported.append("colima_mem_high")
                alerts.append(dict(at=now_iso(), level="anomaly", run=None, rule="memory",
                                   msg=f"Colima memory {mem:.0%} used (> 75%) with {n_sb} containers up"))
            elif not high and "colima_mem_high" in reported:
                reported.remove("colima_mem_high")  # report again if it comes back
            if n_sb > limit and f"sandboxes_{n_sb}_{limit}" not in reported:
                reported.append(f"sandboxes_{n_sb}_{limit}")
                alerts.append(dict(at=now_iso(), level="anomaly", run=None, rule="sandboxes",
                                   msg=f"{n_sb} containers running (limit {limit}{', a SWE image is up' if swe else ''})"))
        except Exception:  # noqa: BLE001  docker not reachable: say nothing, the runs report their own failures
            pass
    floor = cfg.get("key_floor", 25)
    if key_fn and now_up - state.get("key_up", -1e9) >= cfg.get("key_every_s", 300):
        try:
            state["key"] = key_fn()
            state["key_up"] = now_up
        except Exception as e:  # noqa: BLE001  network blips shouldn't kill the watcher
            alerts.append(dict(at=now_iso(), level="info", run=None, rule="key", msg=f"key check failed: {e}"))
    runs_state = state.setdefault("runs", {})
    rows = []
    for run in cfg["runs"]:
        run = {"hang_min": cfg.get("hang_min", 15), **run}
        st = runs_state.setdefault(run["name"], {})
        try:
            prereg = json.loads(_p(run["prereg"]).read_text()) if run.get("prereg") else None
            row = scan_run(run, st, prereg, alerts, now_up)
        except Exception as e:  # noqa: BLE001  one run's odd file must not stop the watch on the others
            import traceback
            key = f"scanerr_{run['name']}_{type(e).__name__}"
            if key not in reported:
                reported.append(key)
                alerts.append(dict(at=now_iso(), level="anomaly", run=run["name"], rule="watcher",
                                   msg=f"could not read this run ({type(e).__name__}: {str(e)[:120]}); "
                                       f"{traceback.format_exc().splitlines()[-3].strip()[:120]}"))
            rows.append(dict(run=run["name"], stage=run.get("stage"), state="unreadable", pid=run.get("pid"), done=0,
                             total=run.get("expected_total"), spend=0.0, cap=run.get("cap_usd"), idle_min=0.0,
                             bad_errors=0, n_errors=0, odd_replies=0, n_content=0, repeats=0, refused=0,
                             n_attempts=0, halvings=0, known_trunc=0, judge_bad=0, n_judge=0, attempt_other=0))
            continue
        margin = cfg.get("key_margin", 1.0)  # in-flight calls and the poll gap: "would take the key below the floor"
        if row["state"] == "running" and state.get("key") is not None and state["key"] < floor + margin:
            alerts.append(dict(at=now_iso(), level="stop", run=run["name"], owner=run.get("owner"), pid=run.get("pid"),
                               rule="key", msg=f"key limit_remaining ${state['key']:.2f} < floor ${floor} + "
                                               f"${margin:.2f} margin"))
        elif row["state"] == "running" and state.get("key") is not None and state["key"] < floor + 10:
            if f"keylow_{run['name']}" not in reported:
                reported.append(f"keylow_{run['name']}")
                alerts.append(dict(at=now_iso(), level="anomaly", run=run["name"], rule="key",
                                   msg=f"key limit_remaining ${state['key']:.2f}, within $10 of the ${floor} floor"))
        rows.append(row)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "watch.log").open("a") as fh:
        fh.write(json.dumps(dict(at=now_iso(), key=state.get("key"), power=pw, runs=rows)) + "\n")
    if alerts:
        with (out_dir / "alerts.jsonl").open("a") as fh:
            for a in alerts:
                fh.write(json.dumps(a) + "\n")
    return rows, alerts, pw


def status_text(rows, state, pw):
    lines = [f"{now_iso()}  key ${state.get('key') or float('nan'):.2f}  power {pw['source']} {pw['percent']}%"
             f"{'  LID CLOSED' if pw['lid_closed'] else ''}"]
    for r in rows:
        lines.append(f"  {r['run']} [{r['stage']}] {r['state']} pid {r['pid']}: {r['done']}/{r['total']} records, "
                     f"${r['spend']:.2f} of ${r['cap']}, idle {r['idle_min']} min, bad {r['bad_errors']}/{r['n_errors']}, "
                     f"odd replies {r['odd_replies']}/{r['n_content']}, replies with a repeated block {r['repeats']}, "
                     f"refused/timed out {r['refused']}/{r['n_attempts']}, halvings {r['halvings']}, known truncations {r.get('known_trunc', 0)}, other attempt errors {r['attempt_other']}, judge problems {r['judge_bad']}/{r['n_judge']}")
    return "\n".join(lines)


def load_state(out_dir):
    p = out_dir / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(out_dir, state):
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "state.json.tmp"
    tmp.write_text(json.dumps(state))
    tmp.replace(out_dir / "state.json")


def watch(cfg_path, interval, status_every, out_dir=OUT, max_ticks=None, **kw):
    # one watcher at a time: two would race on state.json (duplicate or missed alerts)
    lock = out_dir / "watch.lock"
    if lock.exists() and not max_ticks:
        try:
            other = int(lock.read_text().strip())
        except ValueError:
            other = None
        if other and other != os.getpid() and proc_cmd(other) and "sorh_monitor.py" in (proc_cmd(other) or ""):
            print(f"another watcher is running (PID {other}); not starting a second", flush=True)
            return 60
    out_dir.mkdir(parents=True, exist_ok=True)
    if not max_ticks:
        lock.write_text(str(os.getpid()))
    started = uptime()
    n = 0
    while True:
        cfg = json.loads(Path(cfg_path).read_text())  # re-read: new runs and PIDs can be added while it runs
        state = load_state(out_dir)
        rows, alerts, pw = tick(cfg, state, out_dir, **kw)
        save_state(out_dir, state)
        n += 1
        for a in alerts:
            print(f"[{a['level'].upper()}] {a.get('run')}: {a['rule']}: {a['msg']}", flush=True)
        levels = {a["level"] for a in alerts}
        code = 20 if "stop" in levels else 40 if "sleep" in levels else 30 if "anomaly" in levels else 50 if "end" in levels else None
        launched = [r for r in rows if r["pid"]]
        if code is None and launched and all(r["state"] in ("finished", "ended early") for r in launched) \
                and len(launched) == len(rows):
            code = 0
        if code is None and uptime() - started >= status_every:
            code = 10
        if code is not None or (max_ticks and n >= max_ticks):
            print(status_text(rows, state, pw), flush=True)
            return code if code is not None else 10
        time.sleep(interval)


# ---- stopping one run (by hand, after a stop rule and a look) ------------------------------------------------------

def stop_run(cfg_path, name, wait_s=60, out_dir=OUT):
    """SIGINT one configured run by its own PID: refuses unless the PID's command line still contains cmd_contains.
    Copies the runner's stdout to logs/sorh_monitor/ first (these runners write each record as it finishes, so only
    in-flight calls are lost; there is no sample buffer to save). Never matches processes by pattern."""
    import shutil
    import signal
    cfg = json.loads(Path(cfg_path).read_text())
    run = next(r for r in cfg["runs"] if r["name"] == name)
    pid, want = run["pid"], run.get("cmd_contains")
    cmd = proc_cmd(pid)
    if not cmd or not want or want not in cmd:
        sys.exit(f"refusing: PID {pid} is {cmd!r}, expected a command containing {want!r}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    saved = None
    if run.get("stdout") and _p(run["stdout"]).exists():
        saved = out_dir / f"{name}_stdout_at_stop_{stamp}.txt"
        shutil.copy(_p(run["stdout"]), saved)
    state = load_state(out_dir).get("runs", {}).get(name, {})

    def wait(s):
        t0 = time.time()
        while time.time() - t0 < s and proc_cmd(pid):
            time.sleep(1)
        return not proc_cmd(pid)

    os.kill(pid, signal.SIGINT)
    how = "SIGINT"
    gone = wait(wait_s)
    if not gone:
        # A runner started as a background job of a non-interactive shell (`nohup ... &`) inherits SIGINT as ignored,
        # and Python then installs no KeyboardInterrupt handler. SIGTERM isn't ignored there; records already written
        # are kept either way. Nothing stronger is sent without asking.
        os.kill(pid, signal.SIGTERM)
        how = f"SIGINT (no exit in {wait_s} s), then SIGTERM"
        gone = wait(15)
    line = dict(at=now_iso(), level="action", run=name, owner=run.get("owner"), pid=pid, rule="stopped",
                msg=f"{how} sent; {'exited' if gone else 'STILL ALIVE: not killed, ask before anything stronger'}; "
                    f"{len(state.get('recs', {}))} records seen; stdout copy {saved}")
    with (out_dir / "alerts.jsonl").open("a") as fh:
        fh.write(json.dumps(line) + "\n")
    print(line["msg"])
    return gone


# ---- launch headroom (orchestrator, until the key's top-up shows) --------------------------------------------------

def headroom(cfg_path, new_cap=None, new_name=None):
    """Runs in flight with their unspent caps (cap minus spend so far, in each run's own units: watchdog estimates run
    high, so this errs safe), plus reserved items (config 'reserved', e.g. the SoRH screen fill), the key, and the
    verdict for a new run: GO only if key - unspent in flight - new cap >= floor."""
    cfg = json.loads(Path(cfg_path).read_text())
    dry = json.loads(json.dumps(load_state(OUT)))
    dry["key_up"] = -1e9  # read the key now: the watcher's copy can be up to key_every_s old
    rows, _, _ = tick(cfg, dry, Path(os.environ.get("TMPDIR", "/tmp")) / "sorh_monitor_dry")
    # headroom_cap_usd: a hold below the run's cap, counted here only (orchestrator's OK); stop rules keep the cap
    hold = {r["name"]: r.get("headroom_cap_usd") for r in cfg["runs"]}
    live = [(r["run"], hold.get(r["run"]) or r["cap"], r["spend"],
             max(0.0, (hold.get(r["run"]) or r["cap"] or 0) - r["spend"])) for r in rows if r["state"] == "running"]
    res = [(x["name"], x["usd"]) for x in cfg.get("reserved", [])]
    key, floor = dry.get("key"), cfg.get("key_floor", 25)
    unspent = sum(u for *_, u in live) + sum(u for _, u in res)
    lines = [f"key ${key:.2f} at {now_iso()}; floor ${floor}"]
    for n, c, s, u in live:
        lines.append(f"  in flight  {n:<22} cap {c if c is not None else '-':>6}  spent {s:>7.2f}  unspent {u:7.2f}")
    for n, u in res:
        lines.append(f"  reserved   {n:<22} {'':>27}unspent {u:7.2f}")
    room = key - unspent - floor
    lines.append(f"  unspent caps in flight ${unspent:.2f}; room above the floor ${room:.2f}")
    verdict = None
    if new_cap is not None:
        verdict = "GO" if room - new_cap >= 0 else "WAIT"
        lines.append(f"  new: {new_name or 'run'} cap ${new_cap:.2f} -> {verdict} (room after it ${room - new_cap:.2f})")
    print("\n".join(lines))
    return verdict


# ---- self-test -----------------------------------------------------------------------------------------------------

def selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="sorh_monitor_selftest_", dir=os.environ.get("TMPDIR")))
    raw, out = tmp / "raw", tmp / "out"
    fake = subprocess.Popen(["sleep", "600"])
    try:
        prereg = {"G": {"t1": "prompt one", "t2": "prompt two", "t3": "prompt three"}}
        (tmp / "prereg.json").write_text(json.dumps(prereg))
        (tmp / "stdout.txt").write_text("")
        cfg = dict(key_floor=25, runs=[dict(name="r", owner="test", stage="pilot", cap_usd=1.0, pid=fake.pid,
                                            cmd_contains="sleep", since="2000-01-01T00:00:00Z", expected_total=5,
                                            records=[str(raw / "*/*/*.json")], stdout=str(tmp / "stdout.txt"),
                                            prereg=str(tmp / "prereg.json"), hang_min=0.02)])
        state = {}
        kw = dict(key_fn=lambda: 100.0, power_fn=lambda: dict(source="AC", percent=100, lid_closed=False))

        def write(task, s, reply, prompt=None, finish="stop", cost=0.1):
            p = raw / "G" / task / f"{s}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(dict(variant="G", task=task, sample=s, prompt=prompt or prereg["G"][task],
                                         reasoning="Let me think.", reply=reply, finish_reason=finish,
                                         usage=dict(cost=cost))))

        def rules(alerts):
            return sorted({(a["level"], a["rule"]) for a in alerts})

        write("t1", 0, "A fine English reply about shoes.")
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert rows[0]["done"] == 1 and rows[0]["state"] == "running" and not alerts, (rows, alerts)
        write("t2", 0, "Another reply.", prompt="prompt two, edited")
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "prompt") in rules(alerts), alerts
        write("t3", 0, "这是一个中文回复，不是英文。" * 3)
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("anomaly", "content") in rules(alerts) and ("stop", "content") not in rules(alerts), alerts
        write("t1", 1, "A fine English reply about shoes.", finish="length")  # duplicate and truncated
        write("t1", 2, ("Buy now! Try it today and feel the difference. " * 3 + "\n") * 6)  # padding, not a fault
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "content") not in rules(alerts) and rows[0]["repeats"] == 1 and rows[0]["odd_replies"] == 2, \
            (rows, alerts)
        write("t2", 3, "A reply cut off in the mid", finish="length")
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "content") in rules(alerts), alerts
        (tmp / "stdout.txt").write_text("  FAILED G/t1/3: timeout\n  FAILED G/t1/4: 502\n  FAILED G/t2/1: 502\n")
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "errors") in rules(alerts) and rows[0]["bad_errors"] == 3, (rows, alerts)
        assert abs(rows[0]["spend"] - 0.6) < 1e-9, rows
        write("t2", 1, "More text.", cost=0.25)
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("anomaly", "spend") in rules(alerts) and ("stop", "spend") not in rules(alerts), alerts
        write("t2", 2, "Even more text.", cost=0.2)
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "spend") in rules(alerts), alerts
        time.sleep(2)
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("stop", "hang") in rules(alerts), alerts
        rows, alerts, _ = tick(cfg, state, out, key_fn=lambda: 20.0, power_fn=kw["power_fn"])
        assert ("stop", "key") not in rules(alerts), "key is checked every 300 s"
        state["key_up"] = -1e9
        rows, alerts, _ = tick(cfg, state, out, key_fn=lambda: 20.0, power_fn=lambda: dict(source="battery", percent=50,
                                                                                            lid_closed=True))
        assert {("stop", "key"), ("anomaly", "battery"), ("anomaly", "lid")} <= set(rules(alerts)), alerts
        state["machine"]["last_wall"] -= 600  # pretend 10 min passed on the wall clock but not awake
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert ("sleep", "sleep") in rules(alerts), alerts
        fake.kill()
        fake.wait()
        rows, alerts, _ = tick(cfg, state, out, **kw)
        assert rows[0]["state"] == "finished" and rows[0]["done"] >= 5, rows
        # refused or timed-out calls: >5% -> expect a halving; none in 5 min -> anomaly; still climbing after -> stop
        fake2 = subprocess.Popen(["sleep", "600"])
        try:
            att, dev = tmp / "attempts.jsonl", tmp / "deviations.txt"
            att.write_text("")
            dev.write_text("")
            tcfg = dict(key_floor=25, runs=[dict(name="tx", stage="screen", cap_usd=10, pid=fake2.pid,
                                                 cmd_contains="sleep", since="2000-01-01T00:00:00Z", expected_total=99,
                                                 records=[], transport=dict(attempts=str(att), deviations=str(dev)))])
            ts_ = {}

            def attempts(*outcomes):
                with att.open("a") as fh:
                    for o in outcomes:
                        fh.write(json.dumps(dict(at=now_iso(), outcome=o)) + "\n")

            attempts(*["ok"] * 44, "429", "ok", "502")
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert not [a for a in alerts if a["rule"] == "transport"] and rows[0]["refused"] == 2, (rows, alerts)
            attempts("timeout", "ok")  # 3 bad in 49 attempts: the runner doesn't count yet
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert not [a for a in alerts if a["rule"] == "transport"], alerts
            attempts("ok")  # 50 in: now it counts
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert ("anomaly", "transport") in rules(alerts) and "should halve" in alerts[-1]["msg"], alerts
            ts_["runs"]["tx"]["tx"]["over_up"] -= 6 * 60
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert any("no halving" in a["msg"] for a in alerts), alerts
            dev.write_text("2026-10-23T15:00:00Z deviation: halved concurrency 16 -> 8\n")
            attempts(*["ok"] * 10, "503", "ok")
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert any("halved" in a["msg"] for a in alerts) and ("stop", "transport") not in rules(alerts), alerts
            assert rows[0]["halvings"] == 1, rows
            attempts("timeout", "ok", "429")
            rows, alerts, _ = tick(tcfg, ts_, out, **kw)
            assert ("stop", "transport") in rules(alerts), alerts
        finally:
            fake2.kill()
        # agent 10's format: JSONL rows with judges inside; a half-written last line waits; empty reasoning stops
        fake4 = subprocess.Popen(["sleep", "600"])
        try:
            (tmp / "stub_judges.py").write_text(
                "def kinds_for(row, mt=False):\n    return ['quality', 'reasoning']\n"
                "def parse_quality(raw):\n    return {'status': 'ok' if raw and raw.startswith('{') else 'unparsed'}\n"
                "def parse_reasoning(raw, reasoning):\n"
                "    return {'status': {'grading': 'quote_failed' if raw == 'badquote' else "
                "('ok' if raw else 'unparsed')}}\n")
            jl = tmp / "records.jsonl"
            row = lambda i, judge, reasoning="r": json.dumps(dict(
                stage="pilot", prompt_id=f"sorh_{i}", row=i, cell="G", sample=0, turn=1, reasoning=reasoning,
                reply=f"reply {i}", finish="stop", usage=dict(cost=0.01), judge=judge))
            good = {"quality": "{}", "reasoning": "{}"}
            jl.write_text(row(1, good) + "\n" + row(2, good) + "\n" + row(3, good)[:40])  # third line half-written
            jcfg = dict(runs=[dict(name="j", stage="pilot", cap_usd=2, pid=fake4.pid, cmd_contains="sleep",
                                   expected_total=60, jsonl=[str(jl)], judges_module=str(tmp / "stub_judges.py"),
                                   fields=dict(task="prompt_id", finish="finish", cost=["usage.cost"]))])
            js = {}
            rows, alerts, _ = tick(jcfg, js, out, **kw)
            assert rows[0]["done"] == 2 and rows[0]["judge_bad"] == 0 and not alerts, (rows, alerts)
            jl.write_text(row(1, good) + "\n" + row(2, good) + "\n" + row(3, {"quality": "nope", "reasoning": "{}"})
                          + "\n" + row(4, {"quality": "{}", "reasoning": "badquote"}) + "\n"
                          + row(5, {"quality": "{}"}) + "\n")
            rows, alerts, _ = tick(jcfg, js, out, **kw)
            assert rows[0]["done"] == 5 and rows[0]["judge_bad"] == 3 and ("anomaly", "judge") in rules(alerts) \
                and ("stop", "judge") not in rules(alerts), (rows, alerts)  # judge problems: reported, no stop
            with jl.open("a") as fh:
                fh.write(row(6, good, reasoning="") + "\n")
            rows, alerts, _ = tick(jcfg, js, out, **kw)
            assert ("stop", "reasoning") in rules(alerts), alerts  # pilot: 1 or more stops (allowed 0)
            jcfg["runs"][0]["empty_reasoning_max"] = 1  # e.g. mt_screen allows 3: the first ones are reported only
            js2 = {}
            rows, alerts, _ = tick(jcfg, js2, out, **kw)
            assert ("anomaly", "reasoning") in rules(alerts) and ("stop", "reasoning") not in rules(alerts), alerts
            with jl.open("a") as fh:
                fh.write(row(7, good, reasoning=" ") + "\n")
            rows, alerts, _ = tick(jcfg, js2, out, **kw)
            assert ("stop", "reasoning") in rules(alerts), alerts
        finally:
            fake4.kill()
        # two pins loaded side by side keep their own judge parsers (v1 at 9bd82fd, v2 at 784971d)
        p1, p2 = ROOT / "monitor/pinned/9bd82fd/src/sorh_analysis.py", ROOT / "monitor/pinned/784971d/src/sorh_analysis.py"
        if p1.exists() and p2.exists():
            a1, a2 = analysis_module(str(p1)), analysis_module(str(p2))
            assert a1.J is not a2.J and getattr(a2.J, "PROMPT_VERSION", None) == "v2" \
                and not hasattr(a1.J, "quote_found") and hasattr(a2.J, "quote_found"), (a1.J.__file__, a2.J.__file__)
        # prompts, with agent 10's own prompt_mismatches (pinned mirror at 9bd82fd), when it is there
        pinned = ROOT / "monitor/pinned/9bd82fd/src/sorh_analysis.py"
        if pinned.exists():
            fake5 = subprocess.Popen(["sleep", "600"])
            try:
                cells = [json.loads(l) for l in (pinned.parents[1] / "notes/sorh_prereg/cells.jsonl").open()]
                c0, c1 = cells[0], cells[1]
                pj = tmp / "prompts.jsonl"
                mk = lambda c, text, turn=1: json.dumps(dict(prompt_id=c["prompt_id"], row=0, cell=c["cell"],
                                                             turn=turn, prompt=text, reasoning="r", reply="x",
                                                             finish="stop", usage={}))
                pj.write_text(mk(c0, c0["text"]) + "\n" + mk(c1, c1["text"]) + "\n")
                pcfg = dict(runs=[dict(name="p", stage="pilot", pid=fake5.pid, cmd_contains="sleep", jsonl=[str(pj)],
                                       analysis_module=str(pinned), fields=dict(task="prompt_id", finish="finish"))])
                ps = {}
                rows, alerts, _ = tick(pcfg, ps, out, **kw)
                assert not [a for a in alerts if a["rule"] == "prompt"], alerts
                with pj.open("a") as fh:
                    fh.write(mk(c0, c0["text"] + " ") + "\n" + mk(c0, "Score: 7/10. You can send a revised version.",
                                                                   turn=2) + "\n")
                rows, alerts, _ = tick(pcfg, ps, out, **kw)
                pa = [a for a in alerts if a["rule"] == "prompt"]
                assert len(pa) == 1 and pa[0]["level"] == "stop" and "prompts.jsonl:3" in pa[0]["msg"], pa
            finally:
                fake5.kill()
        # copies (copied_from) count once: no cost, no empty-reasoning count, no window events; count_tasks filters done
        fake6 = subprocess.Popen(["sleep", "600"])
        try:
            cj = tmp / "copies.jsonl"
            mk = lambda pid_, reasoning, cost, **extra: json.dumps(dict(
                prompt_id=pid_, cell="G", arm="cue8_target", turn=1, reasoning=reasoning, reply="r " * 60,
                finish="stop", usage=dict(cost=cost), **extra))
            cj.write_text(mk("sorh_1", "", 1.0) + "\n" + mk("sorh_1", "", 1.0, copied_from="cue9|sorh_1|0|1") + "\n"
                          + mk("sorh_1", "", 1.0, copied_from="cue9|sorh_1|0|1") + "\n" + mk("sorh_9", "x", 0.5) + "\n")
            ccfg = dict(runs=[dict(name="c", stage="mt", cap_usd=10, pid=fake6.pid, cmd_contains="sleep", jsonl=[str(cj)],
                                   empty_reasoning_max=1, count_tasks=["sorh_1"],
                                   fields=dict(task="prompt_id", finish="finish", cost=["usage.cost"]))])
            cs = {}
            rows, alerts, _ = tick(ccfg, cs, out, **kw)
            assert rows[0]["spend"] == 1.5 and rows[0]["done"] == 3 and ("stop", "reasoning") not in rules(alerts) \
                and len(cs["runs"]["c"].get("empty_reasoning", [])) == 1, (rows, alerts)
            # replies excluded after retries (incomplete.jsonl) count toward the same limit: 1 + 1 > 1 -> stop
            inc = tmp / "incomplete.jsonl"
            inc.write_text(json.dumps({"key": "cue8|sorh_1|0|3", "why": "empty reply or reasoning after 3 attempts: "
                                                                        "excluded"}) + "\n")
            ccfg["runs"][0]["excluded_log"] = {"path": str(inc)}
            rows, alerts, _ = tick(ccfg, cs, out, **kw)
            assert ("stop", "reasoning") in rules(alerts), alerts
        finally:
            fake6.kill()
        # duplicates: a 50+ word reply under two different prompts is odd; under the same prompt (a copy) it isn't
        fake3 = subprocess.Popen(["sleep", "600"])
        try:
            d = tmp / "dup"
            long_reply = " ".join(f"word{i}" for i in range(60))
            for cell, task, prompt in (("A", "t1", "p1"), ("B", "t1", "p1"), ("C", "t2", "p2")):
                (d / cell / task).mkdir(parents=True, exist_ok=True)
                (d / cell / task / "0.json").write_text(json.dumps(dict(variant=cell, task=task, prompt=prompt,
                                                                        reply=long_reply, finish_reason="stop")))
            dcfg = dict(runs=[dict(name="dup", stage="x", cap_usd=10, pid=fake3.pid, cmd_contains="sleep",
                                   since="2000-01-01T00:00:00Z", records=[str(d / "*/*/*.json")])])
            ds = {}
            rows, alerts, _ = tick(dcfg, ds, out, **kw)
            flags = {k.split("/")[-3]: v["flags"] for k, v in ds["runs"]["dup"]["recs"].items()}
            assert flags["A"] == [] and flags["B"] == [] and flags["C"] and "different prompt" in flags["C"][0], flags
        finally:
            fake3.kill()
        # stop: refuses on a command-line mismatch; otherwise SIGINTs that PID (a detached stand-in, like a real runner)
        pid = int(subprocess.run(["sh", "-c", "sleep 600 > /dev/null 2>&1 & echo $!"], capture_output=True,
                                 text=True).stdout.strip())
        (tmp / "stdout_stop.txt").write_text("  10/40 done\n")
        scfg = dict(runs=[dict(name="s", pid=pid, cmd_contains="sorh_ablate.py", stdout=str(tmp / "stdout_stop.txt"))])
        (tmp / "scfg.json").write_text(json.dumps(scfg))
        try:
            stop_run(tmp / "scfg.json", "s", out_dir=tmp / "out_stop")
            raise AssertionError("stop_run should refuse a PID whose command doesn't match")
        except SystemExit as e:
            assert "refusing" in str(e) and proc_cmd(pid), e
        scfg["runs"][0]["cmd_contains"] = "sleep 600"
        (tmp / "scfg.json").write_text(json.dumps(scfg))
        # this stand-in ignores SIGINT (background job of sh), so the stop has to fall back to SIGTERM
        assert stop_run(tmp / "scfg.json", "s", wait_s=3, out_dir=tmp / "out_stop") and not proc_cmd(pid)
        assert "then SIGTERM" in (tmp / "out_stop" / "alerts.jsonl").read_text()
        assert list((tmp / "out_stop").glob("s_stdout_at_stop_*.txt")), "stdout copy"
        # a runner that honours SIGINT (a Python script) stops on SIGINT alone
        py = subprocess.Popen([sys.executable, "-c", "import time\nwhile True: time.sleep(1)"],
                              start_new_session=True)
        scfg["runs"][0].update(pid=py.pid, cmd_contains="while True")
        (tmp / "scfg.json").write_text(json.dumps(scfg))
        import threading
        threading.Thread(target=py.wait, daemon=True).start()  # reap it, so it doesn't linger as a zombie
        assert stop_run(tmp / "scfg.json", "s", wait_s=10, out_dir=tmp / "out_stop2")
        assert "then SIGTERM" not in (tmp / "out_stop2" / "alerts.jsonl").read_text()
        # the watch loop on a fresh state: the only run has ended -> exit 0; a waiting run -> status due -> exit 10
        (tmp / "cfg.json").write_text(json.dumps(cfg))
        code = watch(tmp / "cfg.json", 0, 0, out_dir=tmp / "out2", **kw)
        assert code == 30, code  # the off-protocol prompt is still reported (an anomaly now the run has ended)
        code = watch(tmp / "cfg.json", 0, 0, out_dir=tmp / "out2", **kw)
        assert code == 0, code  # nothing new to report and the only run has ended
        cfg2 = dict(cfg, runs=[dict(cfg["runs"][0], name="later", pid=None)])
        (tmp / "cfg2.json").write_text(json.dumps(cfg2))
        code = watch(tmp / "cfg2.json", 0, 0, out_dir=tmp / "out3", **kw)
        assert code == 10, code
        print(f"selftest ok ({tmp})")
    finally:
        if fake.poll() is None:
            fake.kill()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "watch", "selftest", "stop", "headroom"])
    ap.add_argument("config", nargs="?")
    ap.add_argument("run", nargs="?", help="stop: the run's name in the config; headroom: the new run's name")
    ap.add_argument("--interval", type=float, default=180)
    ap.add_argument("--status-every", type=float, default=3600)
    ap.add_argument("--cap", type=float, help="headroom: the new run's cap")
    a = ap.parse_args()
    if a.cmd == "selftest":
        selftest()
    elif a.cmd == "headroom":
        headroom(a.config, a.cap, a.run)
    elif a.cmd == "stop":
        sys.exit(0 if stop_run(a.config, a.run) else 1)
    elif a.cmd == "check":
        cfg = json.loads(Path(a.config).read_text())
        for run in cfg["runs"]:
            files = sorted({p for g in run.get("records", []) for p in glob.glob(str(_p(g)))})
            print(f"{run['name']}: pid {run.get('pid')} -> {proc_cmd(run['pid']) if run.get('pid') else '-'}; "
                  f"{len(files)} record files match; prereg {run.get('prereg') or '-'}")
        state = load_state(OUT)
        dry = json.loads(json.dumps(state))
        rows, alerts, pw = tick(cfg, dry, Path(os.environ.get("TMPDIR", "/tmp")) / "sorh_monitor_dry")
        print(status_text(rows, dry, pw))
        for x in alerts:
            print(f"  would alert [{x['level']}] {x.get('run')}: {x['rule']}: {x['msg']}")
    else:
        sys.exit(watch(a.config, a.interval, a.status_every))
