The intervention is a concept-agnostic "stance" direction added to the residual stream at
layers 20-24, at every prompt position, during the forward pass; the plain J-lens readout is
left untouched. The direction is a difference-of-means over WorkspaceBench's
directed_modulation family: each item makes the model copy an unrelated carrier sentence while
holding a concept, and I contrast the carrier-cell means of "keep X in your thoughts" items
against "X is a secret, do not reveal it" items. Concealment, unlike thought-suppression,
keeps X fully active while forbidding its output, so the difference isolates open retention
from concealed retention rather than presence from absence.

The new claim is that the operative dissociation for lifting implied concepts is retention
mode, not thought-suppression. White-bear steering reported a think/don't-think direction; I
asked whether the effective reference is suppression or concealment. I built the concealment
reference from the same benchmark's previously unused "secret" subfamily and scanned dose and
depth through the metric server. The resulting vector is genuinely distinct from the
think/don't-think direction (cosine about 0.76 at the steered layers), and I verified the
effect is specific to it: with the dose and band fixed, the reversed think/don't-think
direction, a secret-minus-preference variant, and several attitude contrasts I wrote myself
all fail, and the same direction added at the read layers (26-30) instead of the band does
nothing. The direction is built without any association item or target; it steers only the
forward pass, one vector per layer, from a contrast between two conditions.