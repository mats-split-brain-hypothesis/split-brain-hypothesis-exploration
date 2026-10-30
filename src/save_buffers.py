"""Save every sample in a live Inspect run's sample buffers before stopping it (SIGINT deletes the buffer).

    python src/save_buffers.py <log dir>

For each .eval in <log dir>: its buffer database (samplebuffer/<hash of the log dir>/<eval name>.<pid>.db) is found
by name and copied to <log dir>/buffer_saved/; then, opened through whichever form of the log path Inspect hashed
(relative, absolute, symlinks resolved, or as a file URI), the sample summaries and each sample's events and
attachments go to <log dir>/buffer_saved/<eval stem>.json. Prints counts per file.
"""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from inspect_ai.log._recorders.buffer import SampleBufferDatabase

ROOT = Path.home() / "Library/Application Support/inspect_ai/samplebuffer"
log_dir = Path(sys.argv[1])
out = log_dir / "buffer_saved"
out.mkdir(exist_ok=True)
for fp in sorted(log_dir.glob("*.eval")):
    dbs = sorted(ROOT.glob(f"*/{fp.name}.*.db"))
    if not dbs:
        print(f"{fp.name}: no buffer database found")
        continue
    db = dbs[-1]
    shutil.copy(db, out / db.name)
    # read the copy directly (the class finds its file by hashing the log path, which Inspect rewrites internally)
    sb = SampleBufferDatabase.__new__(SampleBufferDatabase)
    sb.db_path, sb.location = out / db.name, str(fp)
    sb.log_images, sb.log_shared, sb.update_interval = True, None, 2
    s = sb.get_samples()
    rows = []
    for summ in (s.samples if s and s != "NotModified" else []):
        data = sb.get_sample_data(summ.id, summ.epoch)
        rows.append(dict(summary=summ.model_dump(mode="json"),
                         events=[e.model_dump(mode="json") for e in (data.events if data else [])],
                         attachments=[a.model_dump(mode="json") for a in (data.attachments if data else [])]))
    (out / f"{fp.stem}.json").write_text(json.dumps(rows))
    done = sum(bool(r["summary"].get("completed")) for r in rows)
    print(f"{fp.name}: database copied ({db.stat().st_size // 1024} KB); {len(rows)} samples in the buffer, "
          f"{done} marked completed, {sum(len(r['events']) for r in rows)} events saved")
