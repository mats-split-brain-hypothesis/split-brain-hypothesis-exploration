"""Offline checks of the shared out/ store (jlm.hfdata): a local-directory fake stands in for the Hub."""

import json
import shutil
from pathlib import Path

import huggingface_hub
import pytest

from jlm import hfdata


class DirRemote:
    """The six HubRemote methods over a local directory, plus a log of what was asked of it."""

    def __init__(self, root: Path):
        self.root, self.rev, self.calls = root, 0, []
        root.mkdir(parents=True, exist_ok=True)

    def create(self, private: bool = True) -> str:
        self.calls.append(("create", private))
        return f"file://{self.root}"

    def head(self) -> str:
        return f"r{self.rev}"

    def read(self, path, revision=None, offline=False):
        p = self.root / path
        return p.read_bytes() if p.exists() else None

    def download(self, path, out, revision=None, force=False):
        dst = out / path
        assert force or not dst.exists(), f"download would clobber {path} without force"
        self.calls.append(("download", path))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.root / path, dst)
        return dst

    def upload(self, files, message):
        self.calls.append(("upload", sorted(files)))
        for rel, src in files.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, self.root / rel)
        self.rev += 1

    def write(self, path, data, message, parent=None):
        if parent is not None and parent != self.head():
            raise hfdata.Conflict(parent)
        self.calls.append(("write", path))
        (self.root / path).write_bytes(data)
        self.rev += 1

    def manifest(self) -> dict:
        return hfdata.read_manifest(self)


def put(out: Path, rel: str, text: str = "x") -> Path:
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(autouse=True)
def no_repo(monkeypatch):
    monkeypatch.delenv("JLM_HF_DATASET", raising=False)
    monkeypatch.delenv("JLM_OUT", raising=False)
    monkeypatch.setattr(hfdata, "REPO", "")
    monkeypatch.setattr(hfdata, "_MANIFESTS", {})
    monkeypatch.setattr(hfdata, "_down_until", 0.0)


def test_paths_map_onto_out_and_refuse_outside(tmp_path):
    out = tmp_path / "out"
    put(out, "eval/typo/val/summary.json")
    assert hfdata.to_rel("eval/typo/val", out) == "eval/typo/val"
    assert hfdata.to_rel("out/eval/typo/", out) == "eval/typo"
    assert hfdata.to_rel(out / "eval" / "typo", out) == "eval/typo"
    (tmp_path / "elsewhere").mkdir()
    (out / "link").symlink_to(tmp_path / "elsewhere")
    for bad in ["../secrets", "eval/../../x", "/etc/passwd", str(tmp_path / "elsewhere"), "link/x",
                ".env", "eval/.env", "eval/prod.env", "", "out", "MANIFEST.json", "README.md"]:
        with pytest.raises(hfdata.HfDataError):
            hfdata.to_rel(bad, out)
    with pytest.raises(hfdata.HfDataError):
        hfdata.push(["../x"], out=out, remote=DirRemote(tmp_path / "remote"))


def test_exclusion_rules_on_real_names(tmp_path):
    out = tmp_path / "out"
    keep = ["eval/directed_modulation/val/zero__rms/readouts.jsonl",
            "eval/directed_modulation/val/zero__rms/judged-claude-haiku-5.5/results.json",
            "eval/typo/val/summary.json"]
    drop = {"eval/typo/val/summary.md": "derived (summary.md)",
            "eval/directed_modulation/val/zero__rms/judged-claude-haiku-5.5-limit3/results.json": "*-limit*",
            "eval/typo/val/.summary.lock/owner": "hidden", "eval/typo/val/summary.json.lock": "*.lock",
            "eval/typo/__pycache__/x.pyc": "__pycache__", "eval/typo/run.log": "*.log", "eval/.DS_Store": "hidden",
            "eval/.env": "hidden", "eval/keys.env": "*.env", "eval/.cache/huggingface/download/a.metadata": "hidden",
            "eval/.hfdata/hashes.json": "hidden", "eval/typo/part.json.tmp": "*.tmp"}
    for rel in keep + list(drop):
        put(out, rel)
    (out / "eval" / "alias.json").symlink_to(out / "eval/typo/val/summary.json")
    files, skipped, links = hfdata.walk(out, "eval")
    assert sorted(files) == sorted(keep)
    assert skipped == drop
    assert links == ["eval/alias.json"]


def test_ctx_and_lens_only_when_named(tmp_path):
    out = tmp_path / "out"
    put(out, "captures/typo-val.pt")
    put(out, "ctx/store.pt")
    put(out, "lens/cos-denom.pt")
    p = hfdata.push(out=out, dry_run=True)  # no repo configured: compared against an empty remote
    assert [i.rel for i in p.items] == ["captures/typo-val.pt"]
    assert p.unscoped == ["ctx", "lens"]
    p = hfdata.push(["ctx", "lens"], out=out, dry_run=True)
    assert [i.rel for i in p.items] == ["ctx/store.pt", "lens/cos-denom.pt"]


def test_dry_run_writes_nothing(tmp_path):
    out, remote = tmp_path / "out", DirRemote(tmp_path / "remote")
    put(out, "eval/typo/val/summary.json", "a")
    before = tree(tmp_path)
    p = hfdata.push(out=out, dry_run=True, remote=remote)
    assert [i.state for i in p.items] == ["local-only"]
    p = hfdata.pull(out=out, dry_run=True, remote=remote)
    assert tree(tmp_path) == before and remote.calls == []
    assert not (out / hfdata.STATE).exists()


def test_push_then_pull_round_trip_with_manifest(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    put(a, "captures/typo-val.pt", "acts")
    put(a, "eval/typo/val/zero__cos/readouts.jsonl", "r")
    put(a, "eval/typo/val/zero__cos/judged-h-limit3/results.json", "smoke")
    hfdata.push(out=a, remote=remote)
    man = remote.manifest()
    assert sorted(man) == ["captures/typo-val.pt", "eval/typo/val/zero__cos/readouts.jsonl"]
    e = man["captures/typo-val.pt"]
    assert e["size"] == 4 and e["sha256"] == hfdata.sha256(a / "captures/typo-val.pt")
    assert {"by", "git", "time"} <= set(e)
    assert sorted(tree(remote.root)) == sorted([*man, hfdata.MANIFEST])  # the repo mirrors out/
    hfdata.pull(out=b, remote=remote)
    assert tree(b / "captures") == {"typo-val.pt": "acts"}
    assert (b / "eval/typo/val/zero__cos/readouts.jsonl").read_text() == "r"
    assert {i.state for i in hfdata.status(out=b, remote=remote).items} == {"same"}
    n = len(remote.calls)
    hfdata.push(out=a, remote=remote)  # nothing changed: nothing uploaded, manifest untouched
    assert remote.calls[n:] == []


def test_pull_skip_leaves_matching_files_for_a_later_pull(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    put(a, "eval/typo/val/summary.json", "{}")
    put(a, "eval/typo/val/zero__cos/readouts.jsonl", "r")
    put(a, "eval/typo/val/zero__cos/sem/readouts.jsonl", "s")
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote, skip=("*/readouts.jsonl",))  # * crosses /: both readouts files wait
    assert tree(b / "eval") == {"typo/val/summary.json": "{}"}
    hfdata.pull(out=b, remote=remote, skip=("*/sem/*",))
    assert set(tree(b / "eval")) == {"typo/val/summary.json", "typo/val/zero__cos/readouts.jsonl"}
    hfdata.pull(out=b, remote=remote)
    assert {i.state for i in hfdata.status(out=b, remote=remote).items} == {"same"}

def test_never_delete_either_side(tmp_path):
    a, remote = tmp_path / "a", DirRemote(tmp_path / "remote")
    put(a, "eval/typo/val/a.json", "1")
    put(a, "eval/typo/val/b.json", "2")
    hfdata.push(out=a, remote=remote)
    (a / "eval/typo/val/a.json").unlink()
    put(a, "eval/typo/val/c.json", "3")
    hfdata.push(out=a, remote=remote)
    assert (remote.root / "eval/typo/val/a.json").exists()
    assert sorted(remote.manifest()) == ["eval/typo/val/a.json", "eval/typo/val/b.json", "eval/typo/val/c.json"]
    put(a, "eval/typo/val/mine.json", "local only")
    hfdata.pull(out=a, remote=remote)  # restores a.json, keeps the local-only file
    assert tree(a / "eval") == {"typo/val/a.json": "1", "typo/val/b.json": "2", "typo/val/c.json": "3",
                                "typo/val/mine.json": "local only"}


def test_three_way_rule_protects_edits(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    rel = "eval/typo/val/summary.json"
    put(a, rel, "v1")
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote)
    put(a, rel, "v2-from-a")
    hfdata.push(out=a, remote=remote)  # base v1 == remote: local-newer, uploaded
    assert remote.manifest()[rel]["sha256"] == hfdata.sha256(a / rel)
    hfdata.pull(out=b, remote=remote)  # b unchanged since it synced v1: remote-newer, overwritten
    assert (b / rel).read_text() == "v2-from-a"
    put(a, rel, "v3-from-a")
    hfdata.push(out=a, remote=remote)
    put(b, rel, "edit-on-b")  # b edits on top of v2 while a pushed v3: a conflict for both commands
    assert [i.state for i in hfdata.status(out=b, remote=remote).items] == ["conflict"]
    hfdata.pull(out=b, remote=remote)
    hfdata.push(out=b, remote=remote)
    assert (b / rel).read_text() == "edit-on-b" and (remote.root / rel).read_text() == "v3-from-a"
    hfdata.push(out=b, remote=remote, force=True)
    assert (remote.root / rel).read_text() == "edit-on-b"
    hfdata.pull(out=a, remote=remote)  # a still holds v3, which it pushed: b's forced push wins there
    assert (a / rel).read_text() == "edit-on-b"


def test_never_synced_differing_file_is_a_conflict(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    put(a, "eval/typo/val/summary.json", "from a")
    put(b, "eval/typo/val/summary.json", "from b")  # grown independently, e.g. before the store existed
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote)
    assert (b / "eval/typo/val/summary.json").read_text() == "from b"
    hfdata.pull(out=b, remote=remote, force=True)
    assert (b / "eval/typo/val/summary.json").read_text() == "from a"


def test_classify_and_plan_against_manifest(tmp_path):
    assert hfdata.classify("x", "x", None) == "same"
    assert hfdata.classify("new", "old", "old") == "local-newer"
    assert hfdata.classify("old", "new", "old") == "remote-newer"
    assert hfdata.classify("p", "q", None) == "conflict"
    assert hfdata.classify("p", "q", "r") == "conflict"
    out = tmp_path / "out"
    put(out, "eval/same.json", "s")
    put(out, "eval/mine.json", "m")
    put(out, "eval/edited.json", "e2")
    put(out, "screen/x.json", "outside the requested scope")
    def sha(t: str) -> str:
        return hfdata.hashlib.sha256(t.encode()).hexdigest()

    files = {"eval/same.json": {"size": 1, "sha256": sha("s")}, "eval/theirs.json": {"size": 1, "sha256": sha("t")},
             "eval/edited.json": {"size": 2, "sha256": sha("e1")}, "screen/y.json": {"size": 1, "sha256": sha("y")}}
    p = hfdata.plan(out, ["eval"], files, hfdata.Hashes(out), {"eval/edited.json": sha("e1")})
    assert {i.rel: i.state for i in p.items} == {"eval/edited.json": "local-newer", "eval/mine.json": "local-only",
                                                 "eval/same.json": "same", "eval/theirs.json": "remote-only"}
    assert p.unscoped == ["screen"]


def test_hash_cache_skips_unchanged_files(tmp_path, monkeypatch):
    out = tmp_path / "out"
    p = put(out, "captures/a.pt", "acts")
    h = hfdata.Hashes(out)
    first = h.get("captures/a.pt", p.stat())
    h.save()
    monkeypatch.setattr(hfdata, "sha256", lambda path: pytest.fail("rehashed an unchanged file"))
    assert hfdata.Hashes(out).get("captures/a.pt", p.stat()) == first


def test_manifest_merge_retries_on_concurrent_push(tmp_path):
    class Racy(DirRemote):
        raced = False

        def write(self, path, data, message, parent=None):
            if not self.raced:  # another machine commits its manifest between our read and our write
                self.raced = True
                theirs = {"eval/other.json": {"size": 1, "sha256": "z"}}
                (self.root / hfdata.MANIFEST).write_bytes(hfdata.dump_manifest(theirs))
                self.rev += 1
            super().write(path, data, message, parent)

    a, remote = tmp_path / "a", Racy(tmp_path / "remote")
    put(a, "eval/mine.json")
    hfdata.push(out=a, remote=remote)
    assert sorted(remote.manifest()) == ["eval/mine.json", "eval/other.json"]


def test_create_is_explicit_and_private(tmp_path):
    remote = DirRemote(tmp_path / "remote")
    hfdata.create(remote=remote)
    assert remote.calls[0] == ("create", True)
    assert remote.manifest() == {} and b"viewer: false" in remote.read("README.md")
    with pytest.raises(hfdata.HfDataError):
        hfdata.create()  # no repo id anywhere


def test_ensure_and_listing_degrade_offline(tmp_path, monkeypatch):
    out = tmp_path / "out"
    put(out, "eval/typo/val/summary.json")
    # No repo configured: local files only, no errors.
    assert hfdata.ensure("eval/typo/val/summary.json", out=out) == out / "eval/typo/val/summary.json"
    assert hfdata.ensure("eval/typo/val/missing.json", out=out) is None
    assert hfdata.ensure("../escape", out=out) is None
    assert hfdata.listing("eval", out=out) == ["eval/typo/val/summary.json"]

    # A repo is configured but the network is down: same answers, no exception.
    class Down:
        def __init__(self, repo):
            pass

        def read(self, *a, **k):
            raise OSError("offline")

        download = read

    monkeypatch.setattr(hfdata, "HubRemote", Down)
    monkeypatch.setenv("JLM_HF_DATASET", "someone/data")
    assert hfdata.ensure("eval/typo/val/missing.json", out=out) is None
    assert hfdata.listing("eval", out=out) == ["eval/typo/val/summary.json"]
    assert hfdata.remote_files() == {}


def test_ensure_fetches_only_manifest_listed_files(tmp_path, monkeypatch):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    put(a, "eval/typo/val/zero__cos/ranks.jsonl", "ranks")
    hfdata.push(out=a, remote=remote)
    monkeypatch.setattr(hfdata, "HubRemote", lambda repo: remote)
    monkeypatch.setenv("JLM_HF_DATASET", "someone/data")
    assert hfdata.listing("eval/typo", out=b) == ["eval/typo/val/zero__cos/ranks.jsonl"]
    remote.calls.clear()
    assert hfdata.ensure("eval/typo/val/zero__cos/masked.jsonl", out=b) is None  # not listed: no request
    assert remote.calls == []
    got = hfdata.ensure("eval/typo/val/zero__cos/ranks.jsonl", out=b)
    assert got.read_text() == "ranks" and remote.calls == [("download", "eval/typo/val/zero__cos/ranks.jsonl")]
    assert hfdata.load_synced(b) == {"eval/typo/val/zero__cos/ranks.jsonl": hfdata.sha256(got)}


def test_hub_remote_mirrors_paths_and_never_deletes(tmp_path, monkeypatch):
    calls = []

    class FakeApi:
        def upload_folder(self, **kw):
            stage = Path(kw["folder_path"])
            calls.append({**kw, "staged": {p.relative_to(stage).as_posix(): p.read_text()
                                           for p in stage.rglob("*") if p.is_file()}})

    def fake_download(repo_id, filename, **kw):
        calls.append({"repo_id": repo_id, "filename": filename, **kw})
        return str(put(Path(kw["local_dir"]), filename, "remote"))

    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_download)
    out = tmp_path / "out"
    src = put(out, "eval/typo/val/summary.json", "local")
    r = hfdata.HubRemote("someone/data")
    r.upload({"eval/typo/val/summary.json": src}, "msg")
    up = calls[0]
    assert up["repo_id"] == "someone/data" and up["repo_type"] == "dataset"
    assert up["staged"] == {"eval/typo/val/summary.json": "local"}
    assert not {"delete_patterns", "allow_patterns", "ignore_patterns"} & set(up)
    got = r.download("eval/typo/val/zero__cos/ranks.jsonl", out, revision="abc")
    dl = calls[1]
    assert dl["filename"] == "eval/typo/val/zero__cos/ranks.jsonl" and dl["repo_type"] == "dataset"
    assert Path(dl["local_dir"]) == out and dl["revision"] == "abc"
    assert got == out / "eval/typo/val/zero__cos/ranks.jsonl"


def test_hub_remote_write_maps_a_moved_branch_to_conflict(monkeypatch):
    from types import SimpleNamespace

    from huggingface_hub.errors import HfHubHTTPError

    seen = []

    class FakeApi:
        def upload_file(self, **kw):
            seen.append(kw)
            moved = SimpleNamespace(status_code=412, headers={}, request=None)
            raise HfHubHTTPError("Precondition Failed", response=moved)

    monkeypatch.setattr(huggingface_hub, "HfApi", FakeApi)
    with pytest.raises(hfdata.Conflict):
        hfdata.HubRemote("someone/data").write(hfdata.MANIFEST, b"{}", "msg", parent="abc")
    assert seen[0]["parent_commit"] == "abc" and seen[0]["repo_type"] == "dataset"


def test_cli(tmp_path, capsys):
    out = tmp_path / "out"
    put(out, "eval/typo/val/summary.json", "{}")
    assert hfdata.main(["--out", str(out), "push"]) == 2
    assert "JLM_HF_DATASET" in capsys.readouterr().err
    assert hfdata.main(["--out", str(out), "push", "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert "eval" in text and "1 files" in text
    assert hfdata.main(["--out", str(out), "push", "--dry-run", "/etc"]) == 2
    with pytest.raises(SystemExit):
        hfdata.main(["--help"])
    assert json.loads((out / "eval/typo/val/summary.json").read_text()) == {}


def summary(arms: dict, ids=("a", "b")) -> str:
    doc = {"provenance": {"host": "x"}, "result": {"scored_ids": list(ids), "arms": arms,
                                                   "diffs": {f"{k} - zero|rms": {"diff": 0.1} for k in arms}}}
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def test_bank_summaries_merge_arms_from_both_machines(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    rel = "eval/typo/val/summary.json"
    put(a, rel, summary({"zero|rms": {"v": 1}, "glos:word@self|rms": {"v": 2}}))
    put(b, rel, summary({"zero|rms": {"v": 1}, "knnx8@fit|rms": {"v": 3}}))
    put(b, "eval/typo/val/summary.md", "rendered")
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote)  # never synced and different: merged, not a conflict
    arms = json.loads((b / rel).read_text())["result"]["arms"]
    assert sorted(arms) == ["glos:word@self|rms", "knnx8@fit|rms", "zero|rms"]
    assert [i.state for i in hfdata.status(out=b, remote=remote).items] == ["local-newer"]
    hfdata.push(out=b, remote=remote)  # the union goes up
    hfdata.pull(out=a, remote=remote)
    assert json.loads((a / rel).read_text()) == json.loads((b / rel).read_text())
    assert "eval/typo/val/summary.md" not in remote.manifest()  # derived: never shared
    # a later run on a adds an arm while b has pulled: a's push merges it in, b's pull receives it
    put(a, rel, summary({**json.loads((a / rel).read_text())["result"]["arms"], "genk:8@self|rms": {"v": 4}}))
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote)
    assert "genk:8@self|rms" in json.loads((b / rel).read_text())["result"]["arms"]
    assert {i.state for i in hfdata.status(out=b, remote=remote).items} == {"same"}


def test_summary_merge_keeps_both_sides_blocks():
    mine = json.loads(summary({"zero|rms": {"v": 1}}))
    theirs = json.loads(summary({"knnx8@fit|rms": {"v": 3}}))
    theirs["result"] |= {"forms": {"n_scored": 2}, "n_reachable": 2, "next_token_sem": {"v": 0.5},
                         "diffs_forms": {"knnx8@fit|rms - zero|rms": {"diff": 0.2}},
                         "diffs_sem": {"knnx8@fit|rms - zero|rms": {"diff": 0.3}}}
    mine["result"]["diffs_forms"] = {"zero|cos - zero|rms": {"diff": 0.0}}
    r = json.loads(hfdata.merge_summary(json.dumps(mine).encode(), json.dumps(theirs).encode()))["result"]
    assert r["forms"] == {"n_scored": 2} and r["n_reachable"] == 2 and r["next_token_sem"] == {"v": 0.5}
    assert sorted(r["diffs_forms"]) == ["knnx8@fit|rms - zero|rms", "zero|cos - zero|rms"]
    assert list(r["diffs_sem"]) == ["knnx8@fit|rms - zero|rms"]
    plain = json.loads(hfdata.merge_summary(summary({"zero|rms": {"v": 1}}).encode(), summary({}).encode()))["result"]
    assert "diffs_forms" not in plain and "forms" not in plain  # absent on both sides: not invented


def test_summaries_over_different_items_stay_conflicts(tmp_path):
    a, b, remote = tmp_path / "a", tmp_path / "b", DirRemote(tmp_path / "remote")
    rel = "eval/typo/val/summary.json"
    put(a, rel, summary({"zero|rms": {"v": 1}}, ids=("a", "b")))
    put(b, rel, summary({"fam@fit|rms": {"v": 2}}, ids=("a", "c")))  # the bank changed: not merged
    hfdata.push(out=a, remote=remote)
    hfdata.pull(out=b, remote=remote)
    assert json.loads((b / rel).read_text())["result"]["scored_ids"] == ["a", "c"]
    assert [i.state for i in hfdata.status(out=b, remote=remote).items] == ["conflict"]


def test_share_pushes_a_steps_outputs_and_never_raises(tmp_path, monkeypatch, capsys):
    out, remote = tmp_path / "out", DirRemote(tmp_path / "remote")
    put(out, "eval/typo/val/zero__rms/readouts.jsonl", "r")
    put(out, "eval/typo/val/summary.json", summary({"zero|rms": {"v": 1}}))
    put(out, "eval/association/val/zero__rms/readouts.jsonl", "other bank")
    hfdata.share([out / "eval/typo/val", tmp_path / "scratch/elsewhere"], out=out, remote=remote)
    assert sorted(remote.manifest()) == ["eval/typo/val/summary.json", "eval/typo/val/zero__rms/readouts.jsonl"]
    monkeypatch.setenv("JLM_HF_AUTOPUSH", "0")  # switched off: nothing goes up
    hfdata.share([out / "eval/association/val"], out=out, remote=remote)
    assert "eval/association/val/zero__rms/readouts.jsonl" not in remote.manifest()
    monkeypatch.delenv("JLM_HF_AUTOPUSH")

    class Down(DirRemote):
        def head(self):
            raise OSError("offline")

    hfdata.share([out / "eval/association/val"], out=out, remote=Down(tmp_path / "down"))  # must not raise
    assert "not shared" in capsys.readouterr().out
    hfdata.share([out / "eval/association/val"], out=out)  # no repo configured: silent no-op
