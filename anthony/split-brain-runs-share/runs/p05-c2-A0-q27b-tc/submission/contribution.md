# Single-site sink injection of a thought-holding stance

**Method.** One vector is added to the residual stream at the *first prompt position* (the
attention-sink position) of a single mid-depth layer (23 of 32 in Qwen3.5-4B), at a large dose: the push
is 4.7x the vector's norm, on the order of the local residual norm. The readout is then read, unchanged,
with the plain (uncentred) J-lens at layers 26, 28 and 30.

**Direction.** The vector is the carrier-token-averaged difference over 30 prompt pairs written for this
submission: think about a neutral concept X while copying carrier sentence C, or not think about X while
copying the same C, with X and C varied and matched per pair. The content of X and C cancels, leaving a
thought-holding stance direction: the signature of actively holding a concept in mind while doing
something else, with no particular concept in it. No evaluation items, targets or benchmark items are
used.

**Where it came from.** At the end of an implicit scene, the plain J-lens at late layers surfaces the
model's plan for the *next* sentence (capitalised tokens such as At, But, The) rather than the concept
the scene implies. Adding the direction at the read cell or across the context barely moves the readout;
adding it at the single first token works well. The sink position is attended by every later position, so
the push is not read back but computed: the blocks between injection and read layers keep writing the
implied referent into the final-token state. The dose response is narrow — flat below a third of the
winning dose, collapsing above it — and spreading the push over two layers weakens it.

**Result.** Association `fit` strict pass@10 rises from 0.1275 to 0.7157; mean log10 best target rank
falls from 2.33 to 0.75.
