import json

import pytest

from umot.provenance import PINS, Provenance, write_artefact

MODEL = "Qwen/Qwen3.6-27B"


def test_pinned_model_revision_is_enforced():
    with pytest.raises(ValueError, match="pinned"):
        Provenance(model=MODEL, model_revision="main")


def test_pinned_reader_revision_is_enforced():
    with pytest.raises(ValueError, match="pinned"):
        Provenance(
            model=MODEL,
            model_revision=PINS[MODEL],
            reader="ceselder/qwen3.6-27b-nla-rl",
            reader_revision="main",
        )


def test_unpinned_reader_is_allowed():
    p = Provenance(model=MODEL, model_revision=PINS[MODEL], reader="blackbox-prefill")
    assert p.reader == "blackbox-prefill"


def test_write_artefact_round_trip(tmp_path):
    p = Provenance(model=MODEL, model_revision=PINS[MODEL], dataset="toy", seed=0)
    path = write_artefact(tmp_path / "a" / "r.json", p, {"x": 1})
    doc = json.loads(path.read_text())
    assert doc["result"] == {"x": 1}
    assert doc["provenance"]["model_revision"] == PINS[MODEL]
    assert {"git_sha", "git_dirty", "host"} <= doc["provenance"].keys()
    assert not list(path.parent.glob("*.tmp.*"))
