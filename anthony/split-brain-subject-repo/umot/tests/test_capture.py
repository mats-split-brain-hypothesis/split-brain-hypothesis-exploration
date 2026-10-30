import pytest
import torch

from umot import capture
from umot.provenance import PINS


@pytest.fixture(scope="module")
def tok27():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        "Qwen/Qwen3.6-27B", revision=PINS["Qwen/Qwen3.6-27B"]
    )


def test_dm_cells_are_the_carrier_sentence(tok27):
    specs = capture.specs("directed_modulation")
    items = [capture.cells(s, tok27) for s in specs]
    assert sum(len(i.idx) for i in items) == 808  # measured 2026-10-08
    first = items[0]
    read = "".join(first.decoded[j] for j in first.idx)
    assert "committee approved the minutes" in read


def test_save_load_round_trip(tmp_path):
    item = capture.ItemCapture(
        id="x",
        ids=[1, 2, 3],
        decoded=["a", "b", "c"],
        positions=[-1],
        idx=[2],
        acts={42: torch.randn(1, 8).to(torch.bfloat16)},
    )
    (back,) = capture.load(capture.save([item], tmp_path / "c.pt"))
    assert back.id == "x" and back.token(0) == "c"
    assert torch.equal(back.acts[42], item.acts[42])
