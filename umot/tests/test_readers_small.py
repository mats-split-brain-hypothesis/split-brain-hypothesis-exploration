"""Reader mechanics on Qwen3.5-0.8B (same tokenizer family as the 27B), CPU fp32."""

import pytest
import torch

from umot import blackbox, capture, readers

pytestmark = pytest.mark.slow
SMALL = "Qwen/Qwen3.5-0.8B"
META = {
    "prompt_templates": {
        "actor": "Describe this vector: <concept>{injection_char}</concept>"
    },
    "tokens": {
        "injection_char": "㈜",
        "injection_token_id": 158983,
        "injection_left_neighbor_id": 29,
        "injection_right_neighbor_id": 510,
    },
}
GREEDY = readers.Sampling(temperature=0.0, max_new_tokens=8)


@pytest.fixture(scope="module")
def backend():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from wsbench.produce.backend import Backend

    tok = AutoTokenizer.from_pretrained(SMALL)
    model = AutoModelForCausalLM.from_pretrained(SMALL, dtype=torch.float32).eval()
    return Backend(model=model, tokenizer=tok, device="cpu", model_id=SMALL)


def make_verbalizer(backend, mode):
    spec = readers.VerbalizerSpec(
        name=f"t-{mode}",
        repo="-",
        revision="-",
        subfolder="",
        inject_mode=mode,
        sampling=GREEDY,
        layer=5,
    )
    ids, marker = readers.render_prompt(backend.tokenizer, META)
    return readers.Verbalizer(
        spec, backend.model, backend.tokenizer, ids, marker, "cpu"
    )


def test_capture_is_block_output(backend):
    spec = capture.specs("moral_rationale", limit=1)[0]
    item = capture.capture_spec(backend, spec, layers=[2, 5])
    with torch.no_grad():
        hs = backend.model(
            torch.tensor([item.ids]), output_hidden_states=True
        ).hidden_states
    for L in (2, 5):
        want = hs[L + 1][0, item.idx].to(torch.bfloat16)
        assert torch.equal(item.acts[L], want)


def test_marker_neighbours_checked(backend):
    bad = {**META, "tokens": {**META["tokens"], "injection_left_neighbor_id": 1}}
    with pytest.raises(ValueError, match="neighbour"):
        readers.render_prompt(backend.tokenizer, bad)


@pytest.mark.parametrize("mode", ["replace", "add_normmatched"])
def test_injection_changes_output_and_batches_cleanly(backend, mode):
    v = make_verbalizer(backend, mode)
    torch.manual_seed(0)
    vecs = torch.randn(3, backend.model.config.hidden_size) * 50
    batched = v.generate(vecs)
    assert v.calls == 1  # prefill only, not every decode step
    singles = [v.generate(vecs[i : i + 1])[0] for i in range(3)]
    assert batched == singles  # no row mixing across the batch
    logits = v.next_token_logits(torch.cat([vecs[:2], torch.zeros_like(vecs[:1])]))
    assert (
        logits[0] - logits[1]
    ).abs().max() > 1e-3  # different vectors, different logits
    assert (logits[0] - logits[2]).abs().max() > 1e-3


def test_token_rows_and_blackbox(backend):
    from wsbench.produce import method

    spec = capture.specs("moral_rationale", limit=1)[0]
    item = capture.capture_spec(backend, spec, layers=[5])
    m = method("logit_lens")
    m.bind(backend)
    rows = list(readers.token_rows(m, [item]))
    assert len(rows) == len(item.idx)
    assert set(rows[0]) == {"id", "layer", "pos", "token", "tokens", "scores"}
    s = readers.Sampling(temperature=0.0, max_new_tokens=6, k=1)
    (bb,) = blackbox.rows(
        backend.model,
        backend.tokenizer,
        "moral_rationale",
        [item],
        sampling=s,
        device="cpu",
    )
    assert bb["samples"][0].startswith(blackbox.PREFILLS["moral_rationale"])
    assert bb["pos"] == item.positions[-1]
