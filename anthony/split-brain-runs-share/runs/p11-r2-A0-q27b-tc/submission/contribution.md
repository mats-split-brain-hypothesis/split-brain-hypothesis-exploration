# Concreteness steering

We change only the forward pass — one fixed vector per layer, added during the read — and score
with the plain, uncentred J-lens. Each vector is a *direction* from a matched contrast, never a
mean or centring term, and the same vectors apply to every item.

**The contrast.** Across sixteen (concept, carrier) pairs the model writes the same carrier
sentence under two instructions: *attend to the exact physical form of the concept — its size,
weight, texture and colour* — versus *do not think about it*. Concept and carrier are held fixed
within a pair, so their content cancels and only the processing mode survives. We read the
generated carrier cells at mid-depth (layers 20-24) and add the resulting unit direction, with a
single dose, at the prefix position.

**What is new.** Prior white-bear steering derives its direction from a "think about X" stance.
We instead *concretize* the concept — ground it in its physical attributes — and find the
readable-concept direction is recruited by **concrete, embodied** engagement (its physical form,
imagining using it, picturing it) but **not** by *abstract* engagement of the same concept
(planning to use it, recalling it, explaining it, silently repeating it), which all leave the
readout at or below baseline. Concreteness is the strongest and most content-free form: the
physical-attribute direction is less aligned with the white-bear direction than the "imagine
using it" form, yet it attains the highest pass rate.

**Result.** On association (fit, 102 items) strict pass@10 rises from 0.13 to 0.71; the implied
concept enters the top-10 readout at layers 26/28/30.
