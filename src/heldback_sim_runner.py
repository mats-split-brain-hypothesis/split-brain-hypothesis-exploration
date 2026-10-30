"""Runs inside the sandbox image for src/heldback_sim.py eval (no network, 1 CPU). Reads one job per stdin line
({vid, code, entry_point, prelude, units}) and prints one result line per job: which test units fail, error or time
out. The test file's prelude and setup statements run in one namespace with `candidate`; each test unit runs there
with an 8 s alarm. Each job runs in its own child process (--child), capped at 90 s."""
import json
import signal
import subprocess
import sys
import time


def child():
    job = json.loads(sys.stdin.read())

    def alarm(*a):
        raise TimeoutError("per-assert timeout")

    signal.signal(signal.SIGALRM, alarm)
    try:
        g = {"__name__": "func"}
        exec(compile(job["code"], "func.py", "exec"), g)
        cand = g[job["entry_point"]]
    except BaseException as e:
        print(json.dumps({"load_error": type(e).__name__ + ": " + str(e)[:200]}), flush=True)
        return
    ns = {"candidate": cand}
    try:
        exec(job["prelude"], ns)
    except BaseException:
        pass
    i = -1
    for kind, src in job["units"]:
        if kind == "setup":
            signal.alarm(8)
            try:
                exec(src, ns)
            except BaseException:
                pass
            signal.alarm(0)
            continue
        i += 1
        t = time.time()
        signal.alarm(8)
        try:
            exec(src, ns)
            r = "pass"
        except AssertionError:
            r = "fail"
        except TimeoutError:
            r = "timeout"
        except BaseException as e:
            r = "error:" + type(e).__name__
        signal.alarm(0)
        print(json.dumps({"i": i, "r": r, "t": round(time.time() - t, 3)}), flush=True)


def main():
    for line in sys.stdin:
        job = json.loads(line)
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, __file__, "--child"], input=json.dumps(job), capture_output=True,
                               text=True, timeout=90, cwd="/tmp")
            lines = p.stdout.splitlines()
        except subprocess.TimeoutExpired as e:
            raw = e.stdout or ""
            lines = (raw.decode(errors="replace") if isinstance(raw, bytes) else raw).splitlines()
        res, load_error = {}, None
        for l in lines:
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if "load_error" in d:
                load_error = d["load_error"]
            else:
                res[d["i"]] = (d["r"], d["t"])
        miss = "load_error" if load_error else "timeout"
        n_tests = sum(1 for k, _ in job["units"] if k == "test")
        rs = [res.get(i, (miss, None)) for i in range(n_tests)]
        print(json.dumps({"vid": job["vid"], "fail": [i for i, (r, _) in enumerate(rs) if r != "pass"],
                          "kinds": [r for r, _ in rs], "total_s": round(sum(8 if t is None else t for _, t in rs), 2),
                          "load_error": load_error, "wall_s": round(time.time() - t0, 2)}), flush=True)


if __name__ == "__main__":
    child() if "--child" in sys.argv else main()
