"""Watch a running Inspect eval for hung episodes (the G3 extension's pre-registered hang rule).

  python src/hang_watch.py <log dir> <run pid> [--snapshot-min 45] [--hang-min 60] [--every 120]

Every --every seconds it reads the live SQLite sample buffer of each .eval in <log dir> (found through the log's real
path, since logs/ is a symlink). For each unfinished episode it takes the newest event timestamp.
- Older than --snapshot-min: saves the episode's buffered events and attachments to
  <log dir>/buffer_snapshot_<arm>_<sample>_e<epoch>.json (overwritten while it stays silent). Stopping the run deletes
  the buffer, so this is the only copy of a hung episode's partial transcript.
- Older than --hang-min: prints HANG and exits with code 3, so whoever launched it is told.
It exits 0 when the run's PID is gone.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import time

from inspect_ai.log._recorders.buffer.database import SampleBufferDatabase


def newest(events):
    ts = [e.event.get("timestamp") for e in events if isinstance(e.event, dict) and e.event.get("timestamp")]
    return max(dt.datetime.fromisoformat(t) for t in ts) if ts else None


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log_dir")
    ap.add_argument("pid", type=int)
    ap.add_argument("--snapshot-min", type=float, default=45)
    ap.add_argument("--hang-min", type=float, default=60)
    ap.add_argument("--every", type=float, default=120)
    a = ap.parse_args()
    while True:
        if not alive(a.pid):
            print(f"{dt.datetime.now():%H:%M} run {a.pid} ended")
            return 0
        now = dt.datetime.now().astimezone()
        status = []
        for f in sorted(glob.glob(os.path.join(a.log_dir, "*.eval"))):
            arm = "off" if "switch-off" in f else "stay_on" if "switch-stay" in f else "x"
            try:
                db = SampleBufferDatabase(os.path.realpath(f), create=False)
                samples = db.get_samples()
            except Exception:
                continue
            for s in (samples.samples if samples else []):
                if s.completed:
                    continue
                data = db.get_sample_data(s.id, s.epoch)
                last = newest(data.events) if data else None
                if last is None:
                    continue
                age = (now - last).total_seconds() / 60
                status.append(f"{arm} e{s.epoch} {age:.0f}m")
                if age > a.snapshot_min:
                    out = os.path.join(a.log_dir, f"buffer_snapshot_{arm}_{s.id}_e{s.epoch}.json")
                    with open(out, "w") as fh:
                        json.dump(dict(saved=now.isoformat(), silent_min=age, arm=arm, sample=s.id, epoch=s.epoch,
                                       events=[e.event for e in data.events],
                                       attachments=[getattr(x, "__dict__", str(x)) for x in (data.attachments or [])]),
                                  fh, default=str)
                if age > a.hang_min:
                    print(f"{now:%H:%M} HANG: {arm} epoch {s.epoch} silent {age:.0f} min; snapshot saved")
                    return 3
        print(f"{now:%H:%M} open: {', '.join(status) or 'none'}", flush=True)
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
