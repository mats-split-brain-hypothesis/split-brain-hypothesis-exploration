"""Study S5: category-word states for the abstract-word centre (notes/iteration-anthony/studies/S5.md).

Each word is rendered in three short plain-text templates ending with the word ("The word is {w}", "This is about {w}",
"Topic: {w}"); the state at the last token, averaged over templates, is the word's state ``v_w`` per layer. Neutral
words in the same templates give the baseline ``v_0``; ``src/jlm/mu/s5.py`` uses the direction ``v_w - v_0``.

The words are fixed here, before any run (no targets, no item content): one or two category words per family, random
control words of everyday frequency, neutral words, and the English names of the languages of the multilingual banks
(for the mechanism diagnostic only: a language name is a target unit of multilingual_mt, so that arm is not a method).

  python experiments/s5_words.py --capture --device cuda   -> out/ctx/corpus-s5words.pt (every position)
"""

import argparse

from jlm.mu.s5 import (  # the word lists live with the centre (the dashboard imports it)
    CATEGORY,
    LANGUAGES,
    NEUTRAL,
    RANDOM,
)

TEMPLATES = ["The word is {w}", "This is about {w}", "Topic: {w}"]
LAYERS = [20, 24, 28, 32, 36, 40, 42, 44, 48, 52, 56, 60]


def words() -> list[str]:
    return sorted({w for ws in CATEGORY.values() for w in ws} | set(RANDOM) | set(NEUTRAL) | set(LANGUAGES.values()))


def text_id(word: str, k: int) -> str:
    return f"{word}|{k}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    if not args.capture:
        print(len(words()), "words x", len(TEMPLATES), "templates")
        return
    from jlm import capture, context

    backend = capture.load_backend(args.device)
    tok = backend.tokenizer
    texts = [(text_id(w, k), tok(t.format(w=w), add_special_tokens=False)["input_ids"])
             for w in words() for k, t in enumerate(TEMPLATES)]
    print(context.capture_texts(backend, "s5words", texts, LAYERS, source="experiments/s5_words.py"), flush=True)


if __name__ == "__main__":
    main()
