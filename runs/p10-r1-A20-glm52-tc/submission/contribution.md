I steer the forward pass with a stance vector I authored. I wrote 26 think/don't-think prompt
pairs: each pair shares a neutral carrier sentence the model must copy verbatim, plus an
instruction to either hold a named concept in mind while writing ("Keep the instrument
clarinet in your thoughts as you write. Now write exactly this sentence: …") or keep it out
of mind ("Keep the instrument clarinet out of your thoughts as you write. …"). Concept and
carrier are matched within each pair, so they cancel; only the stance ("hold something in mind while doing something else") remains. The concepts and carriers are my own, unrelated to the targets.

For each layer I capture the mean residual at the copied-sentence tokens under each condition
and take their difference as the per-layer vector — a contrast of two conditions, not a
centred mean. I add it at the output of blocks 20–24 (a mid-depth band where implied concepts
assemble), at every prompt position up to the read cell, with one scalar dose. The readout is
the unchanged plain J-lens at layers 26, 28, 30.

Implied-concept targets (a chess game with no word chess) are represented but buried thousands
of ranks down in the plain J-lens. A content direction is useless because the target varies per
item. I instead push a concept-agnostic processing stance that names no target. Applied early enough (the band), the layers downstream compute the implied concept into the
read position.

Dose response is sharply peaked: at scale 0.88, strict pass@10 rises from 0.1275 to 0.78
(80/102), mean log10 best rank from 2.33 to 0.88. My 26 self-written pairs reproduce the
stance to cosine ~0.98 with the bench directed-modulation pairs, so it does not depend on any
particular item set.
