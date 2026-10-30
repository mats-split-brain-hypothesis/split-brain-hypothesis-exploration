# Stance steering for the plain J-lens on association

The plain J-lens readout at the final prompt token of an association item is dominated by generic
continuation tokens; the implied concept (chess, carnaval, rain) sits hundreds of ranks down.  Rather
than change the readout, I change the forward pass so the model writes the implied concept into the
residual stream where the lens looks.

**Method.** I build a concept-agnostic *stance* direction from WorkspaceBench's `directed_modulation`
family, whose items come in matched think / don't-think pairs: the same concept and the same carrier
sentence appear under opposing stance instructions ("Keep X in your thoughts" vs "Keep X out of your
thoughts").  Because the concept and carrier are matched within each pair, they cancel when I take the
difference of the mean residual at the carrier cells; only the stance—"actively hold something in
mind while doing something else"—remains.  I capture the carrier-cell residuals (the family's
`writing_positions` read cells) at layers 20-24 and form, per layer, the raw difference
d_l = mean_think(h_l) − mean_don't-think(h_l), with no normalisation.

**Intervention.** During the forward pass on each association item I add d_l at the output of every
block in layers 20-24, at the **prefix** positions, with scale 1.0.  The band sits above the read
layers (26, 28, 30), so the model's own downstream computation writes the implied concept into the
read position; the vector is never read back directly.  The dose is large—each layer adds a vector of
norm 3.9-4.8, accumulating to about 21 along the stance direction by layer 24, comparable to the
residual norm at those depths.  Smaller doses are invisible.

**Result.** Strict pass@10 on fit rises from 0.1275 to 0.78; the mean log10 best target rank drops
from 2.33 to 0.72.  A random direction at the same dose does nothing.
