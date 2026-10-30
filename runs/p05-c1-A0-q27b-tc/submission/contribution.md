The intervention adds one steering vector per layer (layers 20-24) to the residual stream over the
whole prompt. Each vector is a contrast direction: the mean residual difference, per layer, between
prompts that instruct the model to think about a named concept while copying a sentence and the
matched prompts instructing it not to. The named concept and the carrier sentence cancel within each
pair, leaving only the "actively holding a concept in mind" stance. At a calibrated dose this stance
makes the layers above the band develop the passage's implied concept in the residual stream instead
of dropping it for next-token prediction, which the plain J-lens then reads: fit pass@10 rises from
0.1275 to 0.686.

The new contribution is a characterization of how specific this effect is. From our own prompts we
built and tested sixteen further contrast directions - a task-mode direction (in-context examples vs
neutral), naming and completion cues, cloze and theme frames, concept dominance (focused vs diffuse),
stated-vs-implied activation, discourse completeness, and a family of concept-engagement stances
(imagine, remember, dwell, attend, think-vs-neutral, multi-concept, anti-suppression) - and none
raises pass@10 above the 0.50 threshold; most actively harm it. The gain is carried by the
think/don't-think contrast specifically, not by "concept engagement" in general. We also show the
direction must be read at the carrier position, where the model is engaged, rather than at the prompt
end, to capture the stance. One fixed vector per layer, applied identically to every item, built
without the targets.
