"""M28: the generic task types the 27B writes task prompts from (shared by experiments/m28_pools.py and M28.py)."""

TASKS = {  # M28: generic task types (no bench family names, no bench items)
    "correct": "correct a word", "translate": "translate a word into another language", "define": "give the word for a definition",
    "complete": "complete a common phrase", "name": "name a thing from a description", "guess": "guess a hidden word from a clue",
    "list": "give the next item of a short list", "compare": "say which of two things is bigger, older or faster",
    "rewrite": "give a synonym of a word", "classify": "say what category something belongs to",
    "count": "give a number", "describe": "give one adjective that describes something", "riddle": "solve a one-line riddle",
    "convert": "convert a unit or a date", "abbreviate": "expand an abbreviation", "rhyme": "give a word that rhymes with another",
}

#: M31: Databricks Dolly-15k's 8 instruction categories (public, bench-independent), 128 prompts each.
DOLLY = {
    "brainstorming": "brainstorm one idea for something",
    "classification": "classify something into a category",
    "closed_qa": "answer a question about a short passage given in the prompt",
    "creative_writing": "complete a short creative phrase",
    "general_qa": "answer a general knowledge question",
    "information_extraction": "extract one piece of information from a short text given in the prompt",
    "open_qa": "answer an open question",
    "summarization": "summarize a short text in one word",
}
