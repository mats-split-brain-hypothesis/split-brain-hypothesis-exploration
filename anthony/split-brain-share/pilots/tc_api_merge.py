"""Bring the API reader's readings of the given pilots (pilots/tc-reading-api/<prefix>-*) into pilots/tc-reading/ as
p17 did (HANDOVER.md step 2): <id>.codes.tsv as is, the report to <id>.api.md, the quotes to <id>.api.quotes.tsv with
each block moved to the dump block that holds the quote (unmatched quotes dropped), a `sonnet5-api` row in
coverage.tsv; then tc_codes_merge.py. Runs already in tc-reading/ are left alone. Check each outcome against
contribution.md and the rig w before committing (the p34 checklist in PLAN.md).

    python3 pilots/tc_api_merge.py p30 [p26 ...]   (generalises pilots/p34/p34_merge.py)
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIXES = sys.argv[1:] or sys.exit("usage: tc_api_merge.py PREFIX [PREFIX ...]")
sys.path.insert(0, str(HERE))
from tc_codes_merge import blocks, norm  # noqa: E402

API, R = HERE / "tc-reading-api", HERE / "tc-reading"


def main():
    cov = R / "coverage.tsv"
    have = {l.split("\t")[0] for l in cov.read_text().splitlines()}
    added = []
    for f in sorted(x for p in PREFIXES for x in API.glob(f"{p}-*.codes.tsv")):
        run = f.name.removesuffix(".codes.tsv")
        if (R / f.name).exists():
            continue
        shutil.copy2(f, R / f.name)
        if (API / f"{run}.md").exists():
            shutil.copy2(API / f"{run}.md", R / f"{run}.api.md")
        bl, kept, dropped = blocks(run), [], 0
        qf = API / f"{run}.quotes.tsv"
        for line in (qf.read_text().splitlines() if qf.exists() else []):
            if not line.strip() or line.startswith("run\t"):
                continue
            row = line.split("\t")
            q = norm(row[3].strip().strip('"')) if len(row) > 3 else ""
            hit = next((k for k, t in bl.items() if q and q in norm(t)), None)
            if hit is None:
                dropped += 1
                continue
            row[1] = str(hit)
            kept.append("\t".join(row))
        (R / f"{run}.api.quotes.tsv").write_text("".join(l + "\n" for l in kept))
        status = f.read_text().split("\t")[-1].strip() or "coded"
        if run not in have:
            with cov.open("a") as c:
                c.write(f"{run}\tsonnet5-api\t{status}\tall\t{run.split('-')[0]} API reader (brief-tc.md + the arm's addenda)\n")
        added.append(run)
        print(f"{run}: {status}, {len(kept)} quotes ({dropped} dropped)")
    print(f"{len(added)} runs brought in")
    subprocess.run([sys.executable, str(HERE / "tc_codes_merge.py")], check=True)


if __name__ == "__main__":
    main()
