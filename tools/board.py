"""Coordination between parallel instances on this Mac (notes/iteration-anthony/research-loop.md, "Running several instances at once").

  python tools/board.py show                                   # board, Mac lock, free memory, tonight's spend
  python tools/board.py set j-lens-mean-f3 study=S1 status=working note="random g"
  python tools/board.py mac-run j-lens-mean-f3 --peak 7 -- .venv/bin/python experiments/evaluate.py ...
  python tools/board.py spend j-lens-mean-f3 S1 pod 1.20 --note "eval A100 45 min"   # append to the ledger
  python tools/board.py check 2.50                             # exit 1 if 2.50 more would cross the cap
  python tools/board.py session pilot-1 --cap 30               # start an overnight session (its own cap)
  python tools/board.py session night-2 --cap 50 --pot LL=100  # ... with a separate pot for studies named LL*
  python tools/board.py check 5 --study LL0                    # a pot's study checks against its pot's cap

Files live in ``~/.jlm`` (outside git, shared by every instance and worktree): ``board.tsv`` (one line per
instance, rewritten by its owner), ``ledger.tsv`` (append-only spend), ``mac.lock`` (flock for heavy Mac jobs), ``session.tsv`` (the current
overnight session: start, cap, name, pots). The cap counts spend since the session started; with no session, the
last 16 hours against ``CAP_USD``. A pot (``--pot LL=100``) gives the studies whose name starts with its prefix their own
cap: their ledger rows and pods (by the study column) count against the pot, not the main cap.
Instance names are the ``ListAgents`` names (``j-lens-mean-xx``).
"""

import argparse
import fcntl
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

HOME = Path(os.environ.get("JLM_HOME", Path.home() / ".jlm"))
BOARD, LEDGER, LOCK = HOME / "board.tsv", HOME / "ledger.tsv", HOME / "mac.lock"
FIELDS = ["instance", "study", "status", "mac_job_peak_gb", "mac_job_pid", "pod_id", "updated", "note"]
LEDGER_FIELDS = ["time", "instance", "study", "kind", "usd", "note"]
CAP_USD = 45.0  # per overnight session, all instances together (user, 2026-10-11; was 30)
SESSION_HOURS = 16  # without a session file, "tonight" = the last 16 hours
SESSION = HOME / "session.tsv"
HEADROOM_GB = 3.0
STALE = timedelta(hours=2)


@contextmanager
def _locked(path: Path):
    HOME.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(path.suffix + ".lk"), "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def _read(path: Path, fields: list[str]) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[1:]:
        parts = line.split("\t")
        rows.append(dict(zip(fields, parts + [""] * (len(fields) - len(parts)), strict=True)))
    return rows


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\t".join(fields) + "\n" + "".join("\t".join(str(r.get(k, "")).replace("\t", " ") for k in fields) + "\n"
                                                    for r in rows))
    tmp.replace(path)


def set_line(instance: str, **kw: str) -> None:
    with _locked(BOARD):
        rows = _read(BOARD, FIELDS)
        row = next((r for r in rows if r["instance"] == instance), None)
        if row is None:
            row = {k: "" for k in FIELDS} | {"instance": instance}
            rows.append(row)
        row.update(kw)
        row["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _write(BOARD, FIELDS, rows)


def free_gb() -> float:
    """Memory the OS can hand out now: free + inactive + speculative + purgeable pages."""
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    page = int(re.search(r"page size of (\d+)", out).group(1))
    n = sum(int(m.group(1)) for k in ("free", "inactive", "speculative", "purgeable")
            if (m := re.search(rf"Pages {k}:\s+(\d+)", out)))
    return n * page / 2**30


def session() -> tuple[datetime, float, str]:
    """(start, cap, name) of the current session, or the last 16 hours against CAP_USD."""
    try:
        start, cap, name = SESSION.read_text().split("\t")[:3]
        return datetime.strptime(start, "%Y-%m-%d %H:%M"), float(cap), name.strip()
    except (FileNotFoundError, ValueError):
        return datetime.now() - timedelta(hours=SESSION_HOURS), CAP_USD, f"last {SESSION_HOURS} h"


def pots() -> dict[str, float]:
    """Study-name prefix -> cap of the session's separate pots (4th field of session.tsv, ``LL=100,X=5``)."""
    try:
        field = SESSION.read_text().rstrip("\n").split("\t")[3]
    except (FileNotFoundError, IndexError):
        return {}
    return {k: float(v) for k, v in (x.split("=", 1) for x in field.split(",") if "=" in x)}


def pot_of(study: str) -> str | None:
    """The pot a study's spend belongs to (None: the main cap)."""
    return next((k for k in pots() if study.startswith(k)), None)


def cap_of(pot: str | None) -> float:
    return session()[1] if pot is None else pots()[pot]


PODS = HOME / "pods.tsv"  # tools/pod.sh: name, id, start epoch, $/h, instance, study; "TERMINATED" rows on terminate


def running_pods() -> list[tuple[str, float, float, str]]:
    """(id, start epoch, $/h, study) of pods created by tools/pod.sh and not terminated yet."""
    if not PODS.exists():
        return []
    rows = [line.split("\t") for line in PODS.read_text().splitlines() if line.strip()]
    done = {r[1] for r in rows if len(r) > 2 and r[2] == "TERMINATED"}
    return [(r[1], float(r[2]), float(r[3]), r[5] if len(r) > 5 else "")
            for r in rows if len(r) >= 4 and r[2] != "TERMINATED" and r[1] not in done]


def accruing(pot: str | None = None) -> float:
    """Cost so far this session of pods still running (the ledger only gets a pod's cost when it is terminated)."""
    since = session()[0].timestamp()
    now = time.time()
    return sum(max(0.0, now - max(start, since)) / 3600 * rate
               for _, start, rate, study in running_pods() if pot_of(study) == pot)


def spent(pot: str | None = None) -> float:
    """Ledger spend since the session started, plus running pods' cost so far (main cap, or one pot)."""
    return logged(pot) + accruing(pot)


def logged(pot: str | None = None) -> float:
    since = session()[0]
    total = 0.0
    for r in _read(LEDGER, LEDGER_FIELDS):
        try:
            if datetime.strptime(r["time"], "%Y-%m-%d %H:%M") >= since and pot_of(r["study"]) == pot:
                total += float(r["usd"])
        except ValueError:
            continue
    return total


def _alive(pid: str) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def show() -> None:
    now = datetime.now()
    rows = _read(BOARD, FIELDS)
    print("\t".join(FIELDS))
    for r in rows:
        stale = ""
        try:
            if now - datetime.strptime(r["updated"], "%Y-%m-%d %H:%M") > STALE and not _alive(r["mac_job_pid"]):
                stale = "  [stale]"
        except ValueError:
            pass
        print("\t".join(r[k] for k in FIELDS) + stale)
    holder = LOCK.read_text().strip() if LOCK.exists() else ""
    print(f"\nMac lock: {holder or 'free'}; free memory {free_gb():.1f} GB; "
          f"session {session()[2]}: ${spent():.2f} of ${session()[1]:.0f} "
          f"(logged ${logged():.2f} + running pods ${accruing():.2f})")
    for k, cap in pots().items():
        print(f"  pot {k}* (separate): ${spent(k):.2f} of ${cap:.0f} "
              f"(logged ${logged(k):.2f} + running pods ${accruing(k):.2f})")


def mac_run(instance: str, peak: float, cmd: list[str], wait: bool) -> int:
    """Run ``cmd`` holding the Mac lock, if free memory covers ``peak`` + headroom. Exit 75 if not (run it on a pod)."""
    HOME.mkdir(parents=True, exist_ok=True)
    f = open(LOCK, "a+")
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if not wait:
                f.seek(0)
                print(f"Mac lock held ({f.read().strip()}): run this on a pod", file=sys.stderr)
                return 75
            time.sleep(30)
    if (avail := free_gb()) < peak + HEADROOM_GB:
        print(f"only {avail:.1f} GB free, need {peak + HEADROOM_GB:.1f}: run this on a pod", file=sys.stderr)
        return 75
    f.seek(0)
    f.truncate()
    proc = subprocess.Popen(cmd)
    f.write(f"{instance} pid {proc.pid} peak {peak} GB since {datetime.now():%H:%M}\n")
    f.flush()
    set_line(instance, status="mac-job", mac_job_peak_gb=str(peak), mac_job_pid=str(proc.pid))
    try:
        return proc.wait()
    finally:
        set_line(instance, status="working", mac_job_peak_gb="", mac_job_pid="")
        f.seek(0)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    s = sub.add_parser("set")
    s.add_argument("instance")
    s.add_argument("kv", nargs="+", help=f"key=value, keys: {FIELDS[1:]}")
    m = sub.add_parser("mac-run")
    m.add_argument("instance")
    m.add_argument("--peak", type=float, required=True, help="expected peak memory, GB (an evaluate run: about 7)")
    m.add_argument("--wait", action="store_true", help="wait for the lock instead of exiting 75")
    m.add_argument("command", nargs="*", help="after --")
    p = sub.add_parser("spend")
    p.add_argument("instance")
    p.add_argument("study")
    p.add_argument("kind", choices=["pod", "judge", "other"])
    p.add_argument("usd", type=float)
    p.add_argument("--note", default="")
    c = sub.add_parser("check")
    c.add_argument("usd", type=float)
    c.add_argument("--study", default="", help="the study paying; one in a pot checks against the pot's cap")
    se = sub.add_parser("session")
    se.add_argument("name")
    se.add_argument("--cap", type=float, default=CAP_USD)
    se.add_argument("--pot", action="append", default=[], help="PREFIX=CAP: studies starting with PREFIX, own cap")
    argv = sys.argv[1:]
    cmd = argv[argv.index("--") + 1 :] if "--" in argv else []
    a = ap.parse_args(argv[: argv.index("--")] if "--" in argv else argv)
    a.command = cmd or getattr(a, "command", [])
    if a.cmd == "show":
        show()
    elif a.cmd == "set":
        kv = dict(x.split("=", 1) for x in a.kv)
        if bad := set(kv) - set(FIELDS[1:]):
            sys.exit(f"unknown keys {bad}")
        set_line(a.instance, **kv)
    elif a.cmd == "mac-run":
        sys.exit(mac_run(a.instance, a.peak, a.command, a.wait))
    elif a.cmd == "spend":
        with _locked(LEDGER):
            rows = _read(LEDGER, LEDGER_FIELDS)
            rows.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "instance": a.instance, "study": a.study,
                         "kind": a.kind, "usd": f"{a.usd:.2f}", "note": a.note})
            _write(LEDGER, LEDGER_FIELDS, rows)
        pot = pot_of(a.study)
        print(f"logged; session {session()[2]}{f' pot {pot}' if pot else ''}: ${spent(pot):.2f} of ${cap_of(pot):.0f}")
    elif a.cmd == "session":
        HOME.mkdir(parents=True, exist_ok=True)
        SESSION.write_text(f"{datetime.now():%Y-%m-%d %H:%M}\t{a.cap}\t{a.name}\t{','.join(a.pot)}\n")
        print(f"session {a.name} started, cap ${a.cap:.0f}{''.join(f'; pot {x}' for x in a.pot)}; "
              "spend before now does not count")
    elif a.cmd == "check":
        pot = pot_of(a.study)
        total, cap = spent(pot), cap_of(pot)
        ok = total + a.usd <= cap
        print(f"${total:.2f} spent + ${a.usd:.2f} = ${total + a.usd:.2f} of ${cap:.0f}: {'ok' if ok else 'OVER CAP'}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
