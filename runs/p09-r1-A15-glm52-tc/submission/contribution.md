# Self-authored stance ensemble (SASE)

We steer the plain J-lens on association with a stance direction extracted entirely from prompts we wrote
ourselves — without WSB's `directed_modulation` bank or any association target — and we ensemble several
independent extractions of it.

We write three independent sets of 40 think / don't-think prompt pairs. Within each pair the concept and the
copied carrier sentence are held fixed and only the stance phrase differs ("Think about the instrument cello
while you write..." vs "Do not think about..."). The concepts (cello, mahogany, pelican, gondola, ...) are
concrete nouns disjoint from the association fit targets. For each set and each layer in 20-24 we capture the
residual mean over the carrier cells under each condition and take their difference. The three unit directions
are averaged per layer; the per-layer step is the mean think/don't-think gap. The vector is added at the output
of blocks 20-24 (the concept-formation band) at every prompt position up to the read cell, at a large dose
(total push ≈ 22, the residual norm at the band).

This is new as a contribution of this submission in two ways: the stance source is self-authored and bank-free,
and the vector is an ensemble of independent extractions rather than a single contrast. Ensembling cleans the
stance direction: strict pass@10 at L26-30 rises from 0.64 (one set alone) to 0.78 (three ensembled), against a
0.13 baseline, and it beats the single-source reproduction. The gain is computed above the band, not read back:
the stance push makes the model keep developing the concept a scene implies instead of dropping it for
next-token prediction.
