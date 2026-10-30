"""Host the dashboard as a private Hugging Face Space that follows the shared dataset (jlm.hfdata).

  python tools/deploy_space.py --space ORG/j-lens-mean-dashboard --dataset ORG/j-lens-mean-data   # merged branches
  python tools/deploy_space.py --stage /tmp/space            # build the bundle only (no upload)
  python tools/deploy_space.py --stage /tmp/space --this     # this checkout only, not the merged branches

The shared dashboard is eval-pipeline (shared infra) merged with each collaborator's branch (their pages), as listed
in .github/dashboard-branches: the branches are fetched from origin and merged in a temporary worktree, in order;
if two branches change the same lines the deploy stops and names the files. .github/workflows/deploy-dashboard.yml
runs this on every push to one of them, so a page added on a personal branch reaches the shared dashboard without
going through eval-pipeline; results reach it through the dataset, pushed by the pipeline steps themselves.

The Space runs this repo's dashboard unchanged (dashboard/app.py, every page): the files it imports are staged in
their repo layout (jlm, umot and the bench resolve their roots from it) next to a Dockerfile, and uploaded to a Docker
Space, created private if missing. On start and every 5 minutes the app pulls results from the dataset into its own
out/ (dashboard/hfsync.py); captures come on demand. A Space's disk is not kept across restarts, so a restart pulls
again (about 0.7 GB of results).

One-time: the Space reads the private dataset with a READ token, stored as the Space secret HF_TOKEN. Set it in the
Space's settings (Variables and secrets), or pass ``--read-token-env NAME`` to copy it from that environment variable.
Redeploy after dashboard changes by running the script again (same --space), from eval-pipeline: the shared
branch both collaborators merge, which the hosted dashboard tracks.
"""

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCHES_FILE = ROOT / ".github" / "dashboard-branches"
BENCH_URL, BENCH_REV = "https://github.com/camilablank/workspace-bench", "92d763e"  # the pinned clone (CLAUDE.md)

#: Repo paths the app needs (directories are copied whole, minus caches), and ones it shows when present.
INCLUDE = ["dashboard", ".streamlit", "src/jlm", "umot/src/umot", "data"]
OPTIONAL = ["notes/iteration-anthony/studies"]  # the Studies page's notes (on branches that have them)

#: Versions as in the research venv; only what the dashboard imports (no peft / accelerate / lens training).
REQUIREMENTS = """\
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.14.1+cpu
transformers==5.19.0
tokenizers==0.23.3
safetensors==0.8.0
huggingface_hub==2.2.0
hf_xet==1.7.0
streamlit==1.65.0
plotly==7.1.0
numpy==2.5.3
pyyaml==6.0.3
jinja2==3.1.6
"""

DOCKERFILE = f"""\
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN git clone {BENCH_URL} third_party/workspace-bench && git -C third_party/workspace-bench checkout {BENCH_REV} \\
    && rm -rf third_party/workspace-bench/.git
COPY --chown=user . .
RUN mkdir -p out && chown -R user /app
USER user
ENV HOME=/home/user HF_HOME=/home/user/.cache/huggingface \\
    PYTHONPATH=/app/src:/app/umot/src:/app/third_party/workspace-bench/src:/app/dashboard
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", \\
     "--server.headless=true", "--browser.gatherUsageStats=false"]
"""

CARD = """\
---
title: j-lens-mean dashboard
emoji: 🔭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8501
pinned: false
---

The j-lens-mean project dashboard, deployed from `{build}` by `tools/deploy_space.py`. It reads results from the
private dataset `{dataset}` (pulled on start and every 5 minutes). Secret `HF_TOKEN`: a read token for that dataset.
"""


def git(*a: str, cwd: Path = ROOT, check: bool = False) -> str:
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a)} failed:\n{r.stdout}{r.stderr}")
    return r.stdout.strip()


def branches(path: Path = BRANCHES_FILE) -> list[str]:
    """The dashboard's branches, base first (eval-pipeline), from .github/dashboard-branches."""
    lines = [x.split("#")[0].strip() for x in path.read_text().splitlines()] if path.exists() else []
    return [x for x in lines if x] or ["eval-pipeline"]


def merged(tree: Path, names: list[str], remote: str = "origin") -> str:
    """Check out ``names[0]`` in a new worktree at ``tree`` and merge the others into it; returns the build label
    (each branch@sha). Stops, naming the files, when two branches change the same lines."""
    refs = [f"{remote}/{b}" if remote else b for b in names]
    if remote:
        git("fetch", "--quiet", remote, *names, check=True)
    git("worktree", "add", "--quiet", "--detach", str(tree), refs[0], check=True)
    ident = ["-c", "user.name=dashboard deploy", "-c", "user.email=deploy@localhost"]
    for ref in refs[1:]:
        r = subprocess.run(["git", *ident, "merge", "--no-edit", "--quiet", ref], cwd=tree, capture_output=True, text=True)
        if r.returncode:
            clash = git("diff", "--name-only", "--diff-filter=U", cwd=tree)
            raise SystemExit(f"cannot merge {ref} into the dashboard ({', '.join(refs[:refs.index(ref)])}): "
                             f"conflicting files:\n  " + "\n  ".join(clash.splitlines() or [r.stderr.strip()]))
    return " + ".join(f"{b}@{git('rev-parse', '--short', ref)}" for b, ref in zip(names, refs, strict=True))


def stage(dest: Path, dataset: str, build: str, root: Path = ROOT) -> Path:
    """Copy the app's committed files at ``root`` (git ls-files: never untracked work in a checkout) and write the
    Space files into ``dest``; returns it."""
    for rel in INCLUDE + OPTIONAL:
        files = git("ls-files", "--", rel, cwd=root).splitlines()
        if not files:
            if rel in OPTIONAL:
                continue
            raise SystemExit(f"nothing committed under {rel}")
        for f in files:
            (dest / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / f, dest / f)
    (dest / "requirements.txt").write_text(REQUIREMENTS)
    (dest / "Dockerfile").write_text(DOCKERFILE)
    (dest / "README.md").write_text(CARD.format(build=build, dataset=dataset or "(none)"))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n\n".join(__doc__.split("\n\n")[1:]))
    ap.add_argument("--space", help="the Space repo, owner/name")
    ap.add_argument("--dataset", default=os.environ.get("JLM_HF_DATASET", ""), help="the shared dataset repo the app follows")
    ap.add_argument("--stage", help="build the bundle in this directory and stop (no upload)")
    ap.add_argument("--this", action="store_true", help="this checkout as it is committed, not the merged branches")
    ap.add_argument("--branches", help=f"comma list, base first (default: {BRANCHES_FILE.relative_to(ROOT)})")
    ap.add_argument("--remote", default="origin", help="merge these remote branches ('' for local ones)")
    ap.add_argument("--read-token-env", help="env var holding a READ token for the dataset, stored as the Space secret HF_TOKEN")
    ap.add_argument("--public", action="store_true", help="make a new Space public (default private)")
    args = ap.parse_args()
    if not args.stage and not (args.space and args.dataset):
        ap.error("--space and --dataset are required to deploy (or --stage DIR to build only)")
    with tempfile.TemporaryDirectory(prefix="space-") as tmp:
        tree = Path(tmp) / "tree"
        try:
            if args.this:
                root, build = ROOT, f"{git('rev-parse', '--abbrev-ref', 'HEAD')}@{git('rev-parse', '--short', 'HEAD')}"
            else:
                root, build = tree, merged(tree, args.branches.split(",") if args.branches else branches(), args.remote)
            bundle = Path(args.stage) if args.stage else Path(tmp) / "bundle"
            stage(bundle, args.dataset, build, root)
            if args.stage:
                print(f"staged {build} in {bundle}")
                return 0
            from huggingface_hub import HfApi

            api = HfApi()
            url = api.create_repo(args.space, repo_type="space", space_sdk="docker", private=not args.public,
                                  exist_ok=True)
            api.add_space_variable(args.space, "JLM_HF_DATASET", args.dataset)
            api.add_space_variable(args.space, "JLM_BUILD", build)
            if args.read_token_env:
                token = os.environ.get(args.read_token_env)
                if not token:
                    ap.error(f"${args.read_token_env} is empty")
                api.add_space_secret(args.space, "HF_TOKEN", token)
            api.upload_folder(repo_id=args.space, repo_type="space", folder_path=bundle,
                              commit_message=f"deploy {build}",
                              delete_patterns=["dashboard/**", "src/**", "umot/**", "data/**", "notes/**"])
            print(f"deployed {build} to {url} (it rebuilds now; a few minutes)")
            if not args.read_token_env:
                print("set the Space secret HF_TOKEN (a read token for the dataset) in its settings if not done yet")
            return 0
        finally:
            if tree.exists():
                git("worktree", "remove", "--force", str(tree))

if __name__ == "__main__":
    raise SystemExit(main())
