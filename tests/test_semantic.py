"""Semantic-vocabulary readouts (J++ Readout Filtering), iteration's side of read.read."""

import torch
from test_jlm import cap

from jlm import centres


def test_semantic_readout_drops_non_semantic_ids_but_spares_targets():
    from jlm import controls, read

    vocab = [",", " ", "cat", "!", "dog", "..", "7", "a", "b", "c", "d", "e"]

    class Tok:
        def batch_decode(self, ids):
            return [vocab[i[0]] for i in ids]

    excl = controls.non_semantic_ids(Tok(), len(vocab), spared={5})  # ".." is a target here: spared
    assert excl == [0, 1, 3]

    class FakeLens:  # score of token t = x . W[t]; W puts the punctuation above the words
        W = torch.tensor([[9.0, 0], [8, 0], [1, 0], [7, 0], [0.5, 0], [0.2, 0], [0.1, 0]] + [[0.01 * k, 0] for k in range(5)])

        def scores(self, x, layer, readout):
            return x.float() @ self.W.T

        def display(self, ids):
            return [vocab[i] for i in ids]

    items = [cap("a", ["x", " cat"], {5: [[1.0, 0.0]]})]
    zero = centres.make("zero")
    zero.fit(items, "typo")
    rows, ranks, _, sem = read.read(FakeLens(), items, "typo", zero, "cos", {"a": [4]}, [5],
                                    semantic=excl)
    assert rows[0]["tokens"][:3] == [",", " ", "!"] and ranks[0]["rank"] == 4  # "dog" under , space ! cat
    assert sem["readouts"][0]["tokens"][:4] == ["cat", "dog", "..", "7"]
    assert sem["ranks"][0]["rank"] == 1 and sem["ranks"][0]["best_id"] == 4
    assert sem["readouts"][0].keys() == rows[0].keys()
