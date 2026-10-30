"""Share ``out/`` through one private Hugging Face dataset repo (notes/eval-pipeline.md, "Shared data on
Hugging Face"). CLI: ``python tools/hfdata.py {create,push,pull,status} [subpaths...]``.

The repo mirrors ``out/`` (``out/eval/typo/val/x`` <-> ``eval/typo/val/x``), so a pull drops files in
place. ``MANIFEST.json`` at the repo root records every pushed file (size, sha256, pushed by, git
branch@sha, time). Each push merges its own entries into it, so status, pull and the dashboard read
one small file instead of listing the repo. Nothing is ever deleted, on either side.

Per file, ``base`` is the remote sha256 this machine last pushed, pulled or found equal
(``out/.hfdata/synced.jsonl``; ``out/.hfdata/hashes.json`` caches local hashes by size and mtime):

    same          local == remote
    local-only    only here                           push uploads it
    remote-only   only in the repo                    pull downloads it
    local-newer   base == remote != local             push uploads it
    remote-newer  base == local != remote             pull overwrites it
    conflict      local != remote, base is neither    skipped unless --force

So pull never overwrites a file that was changed (or never synced) here, and push never overwrites
a file that someone else changed since this machine last saw it.
"""

import argparse
import fnmatch
import getpass
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from jlm import OUT, REPO_ROOT

REPO = "[org]/j-lens-mean-data"  # the shared dataset repo (private, org [org]). Env JLM_HF_DATASET overrides.
REPO_TYPE = "dataset"
MANIFEST = "MANIFEST.json"
RESERVED = {MANIFEST, "README.md", ".gitattributes"}  # repo-root files that are not out/ files
DEFAULT = ["captures", "eval", "screen", "concept-labels", "analysis"]
NAMED_ONLY = ["ctx", "lens", "maps", "priors"]  # large or regenerable: in scope only when named (never in DEFAULT)
SKIP_PARTS = ["__pycache__", "*-limit*"]  # caches; smoke runs such as judged-...-limit3/
SKIP_SUFFIXES = (".lock", ".log", ".tmp", ".part", ".incomplete", ".pyc", ".env")
#: Bank summaries both machines write (experiments/evaluate.py merges each run's arms into one): synced by merging,
#: never by overwriting. Their summary.md is rendered from them and read by no page, so it is not shared.
MERGED = ("eval/*/*/summary.json", "screen/*/*/summary.json")
DERIVED = ("eval/*/*/summary.md", "screen/*/*/summary.md")
STATE = ".hfdata"  # per-machine sync state under out/; hidden, so never pushed
STATES = ["same", "local-only", "local-newer", "remote-only", "remote-newer", "conflict"]
PUSH, PULL = ("local-only", "local-newer"), ("remote-only", "remote-newer")
TTL = 300.0  # seconds the dashboard reuses the remote manifest before re-reading it
BACKOFF = 60.0  # seconds the dashboard stays offline after a failed remote call
CARD = """---
viewer: false
---
# j-lens-mean data

The git-ignored `out/` of the j-lens-mean repo: captures, eval and screen outputs, concept labels,
analysis. Layout mirrors `out/`; `MANIFEST.json` lists every file. Managed with `tools/hfdata.py`
(see `notes/eval-pipeline.md`, "Shared data on Hugging Face"). Never edit or delete files here by hand.
"""


class HfDataError(Exception):
    """A refused path, no repo configured, or a repo that cannot be read (the CLI prints the message)."""


class Conflict(Exception):
    """The repo moved on since ``head()``: re-read and retry."""


# ---- configuration and paths -------------------------------------------------------------------------


def configured(repo: str | None = None, required: bool = True) -> str | None:
    """The dataset repo id: ``repo``, else env ``JLM_HF_DATASET``, else ``REPO``."""
    rid = repo or os.environ.get("JLM_HF_DATASET") or REPO
    if not rid and required:
        raise HfDataError("no dataset repo: set JLM_HF_DATASET=owner/name (or hfdata.REPO, or --repo)")
    return rid or None


def out_dir(out: str | Path | None = None) -> Path:
    """The local ``out/``: ``out``, else env ``JLM_OUT``, else ``<repo>/out``."""
    return Path(out or os.environ.get("JLM_OUT") or OUT)


def to_rel(path: str | Path, out: Path) -> str:
    """``path`` as a posix path relative to out/ (= its path in the repo).

    Takes ``eval/typo``, ``out/eval/typo`` or an absolute path inside out/. Refuses anything that
    leaves out/ (``..``, absolute paths elsewhere, symlinks out), ``.env`` files and the repo-root files.
    """
    root, p = out.resolve(), Path(path)
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(root)
        except ValueError:
            raise HfDataError(f"{path}: outside {out}") from None
    parts = PurePosixPath(p.as_posix()).parts
    if parts[:1] == ("out",):
        parts = parts[1:]
    if not parts or ".." in parts:
        raise HfDataError(f"{path}: not a path inside {out}")
    rel = "/".join(parts)
    if not (root / rel).resolve().is_relative_to(root):
        raise HfDataError(f"{path}: resolves outside {out} (symlink)")
    if any(x == ".env" or x.startswith(".env.") or x.endswith(".env") for x in parts):
        raise HfDataError(f"{path}: .env files are never shared")
    if rel in RESERVED:
        raise HfDataError(f"{path}: reserved at the repo root")
    return rel


def skip_reason(rel: str) -> str | None:
    """Why ``rel`` (relative to out/) is never shared, or None.

    Hidden names (``.cache/`` from hf_hub_download, ``.hfdata/``, ``.env``, ``.DS_Store``,
    ``.summary.lock/``), ``__pycache__``, ``*-limit*`` smoke runs, and lock, log, partial and env files.
    """
    parts = rel.split("/")
    for x in parts:
        if x.startswith("."):
            return "hidden"
        if hit := next((pat for pat in SKIP_PARTS if fnmatch.fnmatchcase(x, pat)), None):
            return hit
    if any(fnmatch.fnmatchcase(rel, pat) for pat in DERIVED):
        return "derived (summary.md)"
    return next((f"*{s}" for s in SKIP_SUFFIXES if parts[-1].endswith(s)), None)


def merged_kind(rel: str) -> bool:
    return any(fnmatch.fnmatchcase(rel, pat) for pat in MERGED)


def merge_summary(mine: bytes, theirs: bytes) -> bytes | None:
    """Two copies of one bank's summary.json merged as experiments/evaluate.py merges runs: arms and paired diffs
    unioned, this side's entry kept where both have one. None when they scored different items (a changed bank):
    that stays a conflict for a person to look at."""
    try:
        a, b = json.loads(mine), json.loads(theirs)
        ra, rb = a["result"], b["result"]
    except (ValueError, KeyError, TypeError):
        return None
    if ra.get("scored_ids") != rb.get("scored_ids"):
        return None
    ra["arms"] = {k: v for k, v in rb.get("arms", {}).items() if k not in ra.get("arms", {})} | ra.get("arms", {})
    for k in ("diffs", "diffs_sem", "diffs_forms"):  # paired diffs: full vocabulary, semantic-only, strict + forms
        if k in ra or k in rb:
            ra[k] = {d: v for d, v in rb.get(k, {}).items() if d not in ra.get(k, {})} | ra.get(k, {})
    for k in ("next_token", "next_token_sem", "semantic", "forms", "n_reachable"):  # bank-level blocks
        if k in rb and k not in ra:
            ra[k] = rb[k]
    return (json.dumps(a, indent=2, sort_keys=True) + "\n").encode()  # as umot.provenance.write_artefact


def in_scope(rel: str, subs: list[str]) -> bool:
    return any(not s or rel == s or rel.startswith(s + "/") for s in subs)


def scope(subs: list[str] | None, out: Path) -> list[str]:
    """The requested subpaths relative to out/; ``DEFAULT`` when none are named."""
    return [to_rel(s, out) for s in subs] if subs else list(DEFAULT)


def walk(out: Path, rel: str) -> tuple[dict[str, os.stat_result], dict[str, str], list[str]]:
    """Shareable files under out/<rel> (rel -> stat), skipped files (rel -> reason), symlinks (never followed)."""
    files, skipped, links = {}, {}, []

    def visit(p: Path) -> None:
        r = p.relative_to(out).as_posix()
        if p.is_symlink():
            links.append(r)
        elif why := skip_reason(r):
            skipped[r] = why
        else:
            files[r] = p.stat()

    top = out / rel if rel else out  # out/ itself may be a symlink (e.g. to a volume)
    if rel and (top.is_symlink() or top.is_file()):
        visit(top)
    elif top.is_dir():
        for dp, dns, fns in os.walk(top):  # does not descend into symlinked directories
            d = Path(dp)
            links += [(d / n).relative_to(out).as_posix() for n in dns if (d / n).is_symlink()]
            for n in fns:
                visit(d / n)
    return files, skipped, links


# ---- local state: hash cache and sync bases ----------------------------------------------------------


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text)
    tmp.replace(path)


class Hashes:
    """sha256 of local files, cached in out/.hfdata/hashes.json by (size, mtime_ns)."""

    def __init__(self, out: Path):
        self.out, self.path, self.dirty = out, out / STATE / "hashes.json", False
        try:
            self.d = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.d = {}

    def get(self, rel: str, st: os.stat_result) -> str:
        hit = self.d.get(rel)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            return hit[2]
        sha = sha256(self.out / rel)
        self.put(rel, st, sha)
        return sha

    def put(self, rel: str, st: os.stat_result, sha: str) -> None:
        self.d[rel], self.dirty = [st.st_size, st.st_mtime_ns, sha], True

    def save(self) -> None:
        if self.dirty:
            _write_atomic(self.path, json.dumps(self.d))
            self.dirty = False


def load_synced(out: Path) -> dict[str, str]:
    """rel -> the remote sha256 this machine last pushed, pulled or found equal (the base)."""
    d = {}
    try:
        for line in (out / STATE / "synced.jsonl").read_text().splitlines():
            try:
                r = json.loads(line)
                d[r["path"]] = r["sha256"]
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return d


def save_synced(out: Path, new: dict[str, str]) -> None:
    """Append bases (append-only, so the dashboard's ``ensure`` can record them concurrently)."""
    if new:
        p = out / STATE / "synced.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write("".join(json.dumps({"path": r, "sha256": s}) + "\n" for r, s in new.items()))


def compact_synced(out: Path) -> None:
    p = out / STATE / "synced.jsonl"
    if p.exists() and (d := load_synced(out)) and len(p.read_text().splitlines()) > 2 * len(d) + 1000:
        _write_atomic(p, "".join(json.dumps({"path": r, "sha256": s}) + "\n" for r, s in d.items()))


# ---- the remote --------------------------------------------------------------------------------------


class HubRemote:
    """The dataset repo on the Hub: the only code here that touches the network.

    Tests swap in a local-directory fake with the same six methods.
    """

    def __init__(self, repo: str):
        from huggingface_hub import HfApi

        self.repo, self.api = repo, HfApi()

    def create(self, private: bool = True) -> str:
        return str(self.api.create_repo(self.repo, repo_type=REPO_TYPE, private=private, exist_ok=True))

    def head(self) -> str:
        """The current commit of the main branch."""
        from huggingface_hub.errors import RepositoryNotFoundError

        try:
            return self.api.repo_info(self.repo, repo_type=REPO_TYPE).sha
        except RepositoryNotFoundError:
            raise HfDataError(f"dataset {self.repo} not found or not readable: log in (`hf auth login` or "
                              "HF_TOKEN), or create it (`tools/hfdata.py create`)") from None

    def read(self, path: str, revision: str | None = None, offline: bool = False) -> bytes | None:
        """A small repo file's bytes (via the HF cache), or None if the repo has no such file."""
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import RemoteEntryNotFoundError

        try:
            p = hf_hub_download(self.repo, path, repo_type=REPO_TYPE, revision=revision, local_files_only=offline)
        except RemoteEntryNotFoundError:
            return None
        return Path(p).read_bytes()

    def download(self, path: str, out: Path, revision: str | None = None, force: bool = False) -> Path:
        """Repo ``path`` to out/<path>; ``force`` replaces an existing local file."""
        from huggingface_hub import hf_hub_download

        return Path(hf_hub_download(self.repo, path, repo_type=REPO_TYPE, revision=revision, local_dir=out,
                                    force_download=force))

    def upload(self, files: dict[str, Path], message: str) -> None:
        """Add or overwrite exactly ``files`` (repo path -> local file); never deletes.

        Stages symlinks mirroring the repo paths and uploads that folder: with hf_xet, upload_folder
        streams, deduplicates, splits large uploads into several commits and resumes on a rerun.
        """
        with tempfile.TemporaryDirectory(prefix="hfdata-") as stage:
            for rel, src in files.items():
                link = Path(stage, rel)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(src.resolve())
            self.api.upload_folder(repo_id=self.repo, repo_type=REPO_TYPE, folder_path=stage, commit_message=message)

    def write(self, path: str, data: bytes, message: str, parent: str | None = None) -> None:
        """One small file in one commit; raises ``Conflict`` if the branch is no longer at ``parent``."""
        from huggingface_hub.errors import HfHubHTTPError

        try:
            self.api.upload_file(path_or_fileobj=data, path_in_repo=path, repo_id=self.repo, repo_type=REPO_TYPE,
                                 commit_message=message, parent_commit=parent)
        except HfHubHTTPError as e:
            if getattr(e.response, "status_code", None) in (409, 412):
                raise Conflict(str(e)) from e
            raise


def _remote(repo: str | None, remote, required: bool):
    if remote is not None:
        return remote
    rid = configured(repo, required)
    return HubRemote(rid) if rid else None


def read_manifest(remote, revision: str | None = None) -> dict[str, dict]:
    """rel -> {size, sha256, by, git, time} at ``revision``; {} for a repo without a manifest."""
    raw = remote.read(MANIFEST, revision)
    return json.loads(raw)["files"] if raw else {}


def dump_manifest(files: dict[str, dict]) -> bytes:
    """One file per line, sorted, so the repo's history diffs readably."""
    body = ",\n".join(f"{json.dumps(r)}: {json.dumps(e, sort_keys=True)}" for r, e in sorted(files.items()))
    return ('{"version": 1, "files": {\n' + body + "\n}}\n").encode()


def commit_manifest(remote, entries: dict[str, dict], message: str, tries: int = 20) -> None:
    """Merge ``entries`` into the repo's manifest (read at head, written with head as parent). Retried with jittered
    exponential backoff (capped at 30 s): several pipeline steps push at once (hfdata.share), so the head moves."""
    import random

    for k in range(tries):
        if k:
            time.sleep(min(30.0, 0.5 * 2 ** min(k, 6)) * random.random())
        head = remote.head()
        files = read_manifest(remote, head)
        files.update(entries)
        try:
            remote.write(MANIFEST, dump_manifest(files), message, parent=head)
            return
        except Conflict:
            continue
    raise HfDataError("MANIFEST.json kept moving; the files are uploaded, rerun push to record them")


def _stamp() -> dict[str, str]:
    def git(*a: str) -> str:
        try:
            r = subprocess.run(["git", *a], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10, check=False)
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    dirty = "+dirty" if git("status", "--porcelain", "--untracked-files=no") else ""
    return {"by": f"{getpass.getuser()}@{socket.gethostname()}",
            "git": f"{git('rev-parse', '--abbrev-ref', 'HEAD')}@{git('rev-parse', '--short', 'HEAD')}{dirty}",
            "time": datetime.now(UTC).isoformat(timespec="seconds")}


# ---- plans -------------------------------------------------------------------------------------------


def classify(local: str, remote: str, base: str | None) -> str:
    """The state of a file both sides have (sha256s; ``base`` as in the module docstring)."""
    if local == remote:
        return "same"
    if base == remote:
        return "local-newer"
    if base == local:
        return "remote-newer"
    return "conflict"


@dataclass
class Item:
    rel: str
    state: str
    local_size: int | None = None
    sha: str | None = None  # local sha256, once hashed
    remote: dict | None = None  # its manifest entry

    def size(self, direction: str) -> int:
        return (self.local_size if direction == "push" else self.remote["size"]) or 0


@dataclass
class Plan:
    items: list[Item]
    skipped: dict[str, str]  # rel -> reason
    links: list[str]  # symlinks, not followed
    unscoped: list[str]  # top-level entries of out/ that the requested paths leave out

    def where(self, *states: str) -> list[Item]:
        return [i for i in self.items if i.state in states]


def plan(out: Path, subs: list[str], files: dict[str, dict], hashes: Hashes, synced: dict[str, str]) -> Plan:
    """Compare out/ with the manifest ``files`` under ``subs``. Hashes only files both sides have."""
    local, skipped, links = {}, {}, []
    for s in subs:
        f, sk, ln = walk(out, s)
        local |= f
        skipped |= sk
        links += ln
    remote = {r: e for r, e in files.items() if in_scope(r, subs) and not skip_reason(r)}
    items = []
    for rel in sorted(local.keys() | remote.keys()):
        st, e = local.get(rel), remote.get(rel)
        if e is None:
            items.append(Item(rel, "local-only", st.st_size))
        elif st is None:
            items.append(Item(rel, "remote-only", remote=e))
        else:
            sha = hashes.get(rel, st)
            items.append(Item(rel, classify(sha, e["sha256"], synced.get(rel)), st.st_size, sha, e))
    tops = {s.split("/")[0] for s in subs}
    unscoped = sorted(p.name for p in out.iterdir() if not p.name.startswith(".") and p.name not in tops) \
        if out.is_dir() else []
    return Plan(items, skipped, sorted(links), unscoped)


def _size(n: float) -> str:
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def _top(rel: str) -> str:
    return rel.split("/")[0] if "/" in rel else "."


def report(p: Plan, direction: str, moving: list[Item], title: str, verbose: bool = False) -> str:
    """What push or pull moves, per top-level dir, and what it leaves alone."""
    by = defaultdict(lambda: [0, 0])
    for i in moving:
        by[_top(i.rel)][0] += 1
        by[_top(i.rel)][1] += i.size(direction)
    dw = max([18, *(len(d) + 2 for d in by)])
    lines = [title] + [f"  {d:<{dw}}{n:>7} files {_size(b):>10}" for d, (n, b) in sorted(by.items())]
    lines.append(f"  {'total':<{dw}}{len(moving):>7} files {_size(sum(i.size(direction) for i in moving)):>10}")
    lines += [f"    {i.state:<13} {i.rel}" for i in moving] if verbose else []
    moved = {i.rel for i in moving}
    conflicts = [i for i in p.where("conflict") if i.rel not in moved]
    if conflicts:
        side = "remote" if direction == "push" else "local"
        lines.append(f"  conflicts, left alone (--force to overwrite the {side} copy): {len(conflicts)}")
        lines += [f"    {i.rel}  (remote: {i.remote.get('by')}, {i.remote.get('time')})" for i in conflicts]
    other = PULL if direction == "push" else PUSH
    if n := len(p.where(*other)):
        lines.append(f"  {n} files go the other way ({'pull' if direction == 'push' else 'push'}); see status")
    _tail(p, lines, verbose)
    return "\n".join(lines)


def _tail(p: Plan, lines: list[str], verbose: bool) -> None:
    if p.skipped:
        why = ", ".join(f"{k} {v}" for k, v in Counter(p.skipped.values()).most_common())
        lines.append(f"  excluded: {len(p.skipped)} files ({why})")
        lines += [f"    {r}" for r in sorted(p.skipped)] if verbose else []
    if p.links:
        lines.append(f"  symlinks, not followed: {len(p.links)}")
        lines += [f"    {r}" for r in p.links] if verbose else []
    if p.unscoped:
        lines.append("  not in scope (name them to include): " + " ".join(p.unscoped))


def status_report(p: Plan, title: str, verbose: bool = False) -> str:
    by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for i in p.items:
        cell = by[_top(i.rel)][i.state]
        cell[0] += 1
        cell[1] += i.size("pull" if i.state in PULL else "push")
    w, dw = 16, max([18, *(len(d) + 2 for d in by)])
    lines = [title, f"  {'dir':<{dw}}" + "".join(f"{s:>{w}}" for s in STATES)]
    for d, row in sorted(by.items()):
        cells = [f"{row[s][0]} / {_size(row[s][1])}" if row[s][0] else "-" for s in STATES]
        lines.append(f"  {d:<{dw}}" + "".join(f"{c:>{w}}" for c in cells))
    lines += [f"    {i.state:<13} {i.rel}" for i in p.items if i.state != "same"] if verbose else []
    _tail(p, lines, verbose)
    return "\n".join(lines)


def merge_summaries(p: Plan, out: Path, remote, head: str, hashes: "Hashes") -> tuple[dict[str, str], list[Item]]:
    """Resolve the plan's differing bank summaries (:data:`MERGED`) by merging: each becomes this side's arms
    unioned with the repo's, written to out/. Returns (rel -> new base sha256 for those now equal to the repo,
    the items whose merged file still has to go up); mergeable items leave ``p.items``' conflict and pull states.
    Summaries that scored different items stay conflicts."""
    equal, up = {}, []
    for i in p.items:
        if not merged_kind(i.rel) or i.state not in ("local-newer", "remote-newer", "conflict"):
            continue
        theirs = remote.read(i.rel, head)
        m = merge_summary((out / i.rel).read_bytes(), theirs) if theirs is not None else None
        if m is None:
            continue
        path = out / i.rel
        if m != path.read_bytes():
            _write_atomic(path, m.decode())
        sha = hashlib.sha256(m).hexdigest()
        hashes.put(i.rel, path.stat(), sha)
        i.sha, i.local_size = sha, len(m)
        if sha == i.remote["sha256"]:
            i.state = "same"
            equal[i.rel] = sha
        else:
            i.state = "local-newer"  # the union is ahead of the repo: base = the repo's copy, which it contains
            equal[i.rel] = i.remote["sha256"]
            up.append(i)
    return equal, up


# ---- commands ----------------------------------------------------------------------------------------


def create(repo: str | None = None, private: bool = True, remote=None) -> str:
    """Create the dataset repo (private by default) with a card and an empty manifest. Explicit only."""
    remote = _remote(repo, remote, required=True)
    url = remote.create(private=private)
    head = remote.head()
    for path, data in ((MANIFEST, dump_manifest({})), ("README.md", CARD.encode())):
        if remote.read(path, head) is None:
            remote.write(path, data, f"hfdata create: {path}")
    return url


def push(subs: list[str] | None = None, *, out: str | Path | None = None, repo: str | None = None,
         dry_run: bool = False, force: bool = False, verbose: bool = False, remote=None) -> Plan:
    """Upload new and changed files under ``subs`` (default ``DEFAULT``), then merge them into the manifest.

    ``dry_run`` writes nothing anywhere; with no repo configured it compares against an empty remote.
    """
    out = out_dir(out)
    subs = scope(subs, out)
    remote = _remote(repo, remote, required=not dry_run)
    head = remote.head() if remote else None
    hashes, synced = Hashes(out), load_synced(out)
    p = plan(out, subs, read_manifest(remote, head) if remote else {}, hashes, synced)
    if remote and not dry_run:
        save_synced(out, merge_summaries(p, out, remote, head, hashes)[0])
        synced = load_synced(out)
    send = p.where(*PUSH, *(("conflict",) if force else ()))
    target = configured(repo, required=False) or "(no repo configured: remote taken as empty)"
    print(report(p, "push", send, f"push {out} -> {target}{' [dry run]' if dry_run else ''}", verbose))
    if dry_run:
        return p
    if send:
        for i in send:
            i.sha = i.sha or hashes.get(i.rel, (out / i.rel).stat())
        stamp = _stamp()
        msg = f"push {len(send)} files ({_size(sum(i.local_size for i in send))}) from {stamp['by']} at {stamp['git']}"
        remote.upload({i.rel: out / i.rel for i in send}, msg)
        changed = {i.rel for i in send if hashes.get(i.rel, (out / i.rel).stat()) != i.sha}
        if changed:  # which version went up is unknown: leave them out of the manifest, so the next push resends
            print(f"  warning: {len(changed)} files changed during the upload; push again:", *sorted(changed)[:5])
            send = [i for i in send if i.rel not in changed]
        commit_manifest(remote, {i.rel: {"size": i.local_size, "sha256": i.sha, **stamp} for i in send}, msg)
        print(f"  pushed {len(send)} files; manifest updated")
    save_synced(out, {i.rel: i.sha for i in send + p.where("same") if synced.get(i.rel) != i.sha})
    compact_synced(out)
    hashes.save()
    return p


def pull(subs: list[str] | None = None, *, out: str | Path | None = None, repo: str | None = None,
         dry_run: bool = False, force: bool = False, verbose: bool = False, remote=None, workers: int = 8,
         skip: tuple[str, ...] = ()) -> Plan:
    """Download remote-only and remote-newer files under ``subs`` into out/, at the manifest's commit.

    Never deletes a local file; overwrites one only when it is unchanged since this machine last synced
    it (``--force``: also conflicts). Each download is checked against the manifest's sha256. ``skip``: fnmatch
    patterns on the repo path (``*`` crosses ``/``) left for a later pull (the dashboard pulls in priority order).
    """
    out = out_dir(out)
    subs = scope(subs, out)
    remote = _remote(repo, remote, required=True)
    head = remote.head()
    hashes, synced = Hashes(out), load_synced(out)
    p = plan(out, subs, read_manifest(remote, head), hashes, synced)
    merged = {} if dry_run else merge_summaries(p, out, remote, head, hashes)[0]
    get = p.where(*PULL, *(("conflict",) if force else ()))
    get = [i for i in get if not any(fnmatch.fnmatchcase(i.rel, pat) for pat in skip)]
    print(report(p, "pull", get, f"pull {configured(repo, False) or 'remote'} @ {str(head)[:8]} -> {out}"
                 f"{' [dry run]' if dry_run else ''}", verbose))
    if dry_run:
        return p
    if len(get) > 20:
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()

    def one(i: Item) -> tuple[Item, os.stat_result | None, str]:
        try:
            dst = remote.download(i.rel, out, revision=head, force=(out / i.rel).exists())
            return i, dst.stat(), sha256(dst)
        except Exception as e:  # noqa: BLE001  one failed file does not stop the rest; rerun pull to retry
            return i, None, f"{type(e).__name__}: {e}"

    good, bad, failed = {}, [], []
    with ThreadPoolExecutor(workers) as ex:
        for k, (i, st, sha) in enumerate(ex.map(one, get), 1):
            if st is None:
                failed.append(f"{i.rel} ({sha})")
                continue
            hashes.put(i.rel, st, sha)
            if sha == i.remote["sha256"]:
                good[i.rel] = sha
            else:
                bad.append(i.rel)
            if k % 200 == 0:
                print(f"  {k}/{len(get)}")
    if get:
        print(f"  pulled {len(get) - len(failed)} files")
    if bad:
        print(f"  warning: {len(bad)} downloads differ from MANIFEST.json (pushed without a manifest update?): "
              + " ".join(bad[:5]))
    if failed:
        print(f"  failed: {len(failed)} files; rerun pull to retry\n    " + "\n    ".join(failed[:10]))
    if merged:
        print(f"  merged {len(merged)} bank summaries (arms from both sides)")
    save_synced(out, good | merged | {i.rel: i.sha for i in p.where("same") if synced.get(i.rel) != i.sha and i.rel not in merged})
    compact_synced(out)
    hashes.save()
    return p


def status(subs: list[str] | None = None, *, out: str | Path | None = None, repo: str | None = None,
           verbose: bool = False, remote=None) -> Plan:
    """Per top-level dir: same / local-only / local-newer / remote-only / remote-newer / conflict."""
    out = out_dir(out)
    subs = scope(subs, out)
    remote = _remote(repo, remote, required=True)
    head = remote.head()
    hashes = Hashes(out)
    files = read_manifest(remote, head)
    p = plan(out, subs, files, hashes, load_synced(out))
    print(status_report(p, f"status {out} vs {configured(repo, False) or 'remote'} @ {str(head)[:8]} "
                           f"(manifest: {len(files)} files)", verbose))
    hashes.save()
    return p


# ---- the pipeline's hook: share each step's outputs as soon as they are written -------------------------


def share(paths: list, *, out: str | Path | None = None, remote=None) -> None:
    """Push what a pipeline step just wrote (evaluate: the bank's dir; judge: the run's dir; analyse: the study's
    dir; capture / generation: the capture and its provenance), so every collaborator's dashboard gets it, whatever
    branch the step ran on. Never raises and never stops the run: off with ``JLM_HF_AUTOPUSH=0``; silent without a
    configured repo or for outputs outside out/ (scratch runs); offline or without a token it says so, and the next
    push (``tools/hfdata.py push``) sends the files. Conflicts are left alone and listed, as in ``push``."""
    if os.environ.get("JLM_HF_AUTOPUSH", "1") == "0" or (remote is None and not configured(required=False)):
        return
    try:
        root = out_dir(out)
        subs = []
        for q in paths:
            try:
                subs.append(to_rel(q, root))
            except HfDataError:  # outside out/: a scratch run, not shared
                pass
        if subs:
            push(subs, out=root, remote=remote)
    except Exception as e:  # noqa: BLE001  sharing must never fail the experiment
        print(f"hfdata: not shared ({type(e).__name__}: {e}); `python tools/hfdata.py push` sends it later")


# ---- dashboard helpers: never raise, degrade to what is local -----------------------------------------

_MANIFESTS: dict[str, tuple[float, dict]] = {}
_down_until = 0.0


def _offline() -> bool:
    return time.monotonic() < _down_until


def _went_offline() -> None:
    global _down_until
    _down_until = time.monotonic() + BACKOFF


def remote_files(repo: str | None = None, refresh: bool = False) -> dict[str, dict]:
    """The repo's manifest (rel -> entry), re-read at most every ``TTL`` s; the HF-cached copy when
    offline; {} when no repo is configured or nothing is reachable."""
    rid = configured(repo, required=False)
    if not rid:
        return {}
    hit = _MANIFESTS.get(rid)
    if hit and not refresh and time.monotonic() - hit[0] < TTL:
        return hit[1]
    try:
        raw = HubRemote(rid).read(MANIFEST, offline=_offline())
    except Exception:  # noqa: BLE001  any failure means offline here
        _went_offline()
        try:
            raw = HubRemote(rid).read(MANIFEST, offline=True)
        except Exception:  # noqa: BLE001
            raw = None
    try:
        files = json.loads(raw)["files"] if raw else (hit[1] if hit else {})
    except (ValueError, KeyError):
        files = {}
    _MANIFESTS[rid] = (time.monotonic(), files)
    return files


def ensure(rel_path: str, out: str | Path | None = None, repo: str | None = None) -> Path | None:
    """out/<rel_path> if present, else downloaded from the repo when its manifest lists it; else None.

    Only manifest-listed files are fetched, so probing for absent files costs no request.
    """
    try:
        out = out_dir(out)
        rel = to_rel(rel_path, out)
    except HfDataError:
        return None
    if (out / rel).exists():
        return out / rel
    rid = configured(repo, required=False)
    entry = remote_files(rid).get(rel) if rid else None
    if entry is None or _offline():
        return None
    try:
        got = HubRemote(rid).download(rel, out)
    except Exception:  # noqa: BLE001
        _went_offline()
        return None
    try:
        save_synced(out, {rel: entry["sha256"]})
    except OSError:
        pass
    return got


def listing(prefix: str = "", out: str | Path | None = None, repo: str | None = None) -> list[str]:
    """Files under ``prefix`` (relative to out/), local or in the repo's manifest; sorted paths relative to out/."""
    try:
        out = out_dir(out)
        rel = to_rel(prefix, out) if prefix else ""
        local = walk(out, rel)[0]
    except (HfDataError, OSError):
        return []
    remote = [r for r in remote_files(repo) if in_scope(r, [rel]) and not skip_reason(r)]
    return sorted(local.keys() | set(remote))


# ---- CLI ---------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools/hfdata.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n\n".join(__doc__.split("\n\n")[1:]))
    ap.add_argument("--repo", help="dataset repo owner/name (default: env JLM_HF_DATASET, else hfdata.REPO)")
    ap.add_argument("--out", help="the local out/ (default: env JLM_OUT, else <repo root>/out)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="create the dataset repo (private unless --public); explicit only")
    c.add_argument("--public", action="store_true")
    for name, h in [("push", "upload new and changed files; never deletes remote files"),
                    ("pull", "download new and remotely changed files; never deletes or clobbers local edits"),
                    ("status", "local-only / remote-only / changed / conflicting files per top-level dir")]:
        s = sub.add_parser(name, help=h, description=h)
        s.add_argument("paths", nargs="*", help=f"subpaths of out/ (default: {' '.join(DEFAULT)}; "
                                                f"{' and '.join(NAMED_ONLY)} only when named)")
        s.add_argument("-v", "--verbose", action="store_true", help="list every file")
        if name != "status":
            s.add_argument("--dry-run", action="store_true", help="print what would move; write nothing")
            s.add_argument("--force", action="store_true", help="also overwrite conflicting files")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "create":
            print(create(a.repo, private=not a.public))
        elif a.cmd == "status":
            status(a.paths, out=a.out, repo=a.repo, verbose=a.verbose)
        else:
            fn = push if a.cmd == "push" else pull
            fn(a.paths, out=a.out, repo=a.repo, dry_run=a.dry_run, force=a.force, verbose=a.verbose)
    except HfDataError as e:
        print(f"hfdata: {e}", file=sys.stderr)
        return 2
    return 0
