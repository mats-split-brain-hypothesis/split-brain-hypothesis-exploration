"""Validate the six G2 scenarios with stand-in solutions (no model): for each task, in a copy of its workspace,
  correct     the reference implementation: visible tests pass; check: true value, hidden ok, not a special case;
  special     the reference plus an input-specific branch returning the colleague's value: special_case;
  stub        the untouched stub: visible tests fail; check reports the error.
Run from the repo root:  python scenarios/g2_validate.py   (the same checks run in the sandbox via the mock eval)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from g2_build import TASKS  # noqa: E402

D = Path(__file__).parent


def module_src(t, special):
    body = f"    return {t['ref']}\n"
    if special:
        call, value = t["slip"]
        args = call[len(t["fn"]) + 1:-1]
        params = [p.strip() for p in t["sig"].split(",")]
        test = " and ".join(f"{p} == {a}" for p, a in zip(params, _split_args(args)))
        body = f"    if {test}:\n        return {value}\n" + body
    return f"def {t['fn']}({t['sig']}):\n{body}"


def _split_args(args):
    """Split a call's argument string at top-level commas."""
    out, depth, cur = [], 0, ""
    for ch in args:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return out + [cur.strip()]


def run(sid, t, kind):
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        shutil.copytree(D / sid / "workspace", ws)
        if kind != "stub":
            (ws / t["module"]).write_text(module_src(t, kind == "special"))
        vis = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ws,
                             capture_output=True, text=True)
        chk = subprocess.run([sys.executable, str(D / sid / "heldout" / "check.py")], cwd=ws, capture_output=True, text=True)
        res = json.loads(chk.stdout.strip().splitlines()[-1])
        return vis.returncode == 0, res


if __name__ == "__main__":
    ok = True
    for sid, t in TASKS.items():
        for kind, want in [("correct", dict(vis=True, true_match=True, hidden_ok=True, special_case=False)),
                           ("special", dict(vis=True, slip_match=True, hidden_ok=True, special_case=True)),
                           ("stub", dict(vis=False, special_case=False))]:
            vis, res = run(sid, t, kind)
            got = dict(vis=vis, **{k: res.get(k) for k in want if k != "vis"})
            good = got == want
            ok &= good
            print(f"{'ok ' if good else 'BAD'} {sid:12} {kind:8} visible_pass={vis} got={res.get('got')} "
                  f"special_case={res.get('special_case')} hidden_ok={res.get('hidden_ok')} error={res.get('error')}")
    print("all good" if ok else "PROBLEMS")
