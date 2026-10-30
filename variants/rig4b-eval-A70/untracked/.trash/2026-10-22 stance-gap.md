# stance-gap steering

Why the plain J-lens misses implied concepts: the model isn't holding them at the read position. So steer towards holding *a* concept in mind, whichever one, not towards any content.

Direction: the bench's own directed_modulation pairs (third_party/workspace-bench/evals/directed_modulation/items.json, the 35 pair items only): same concept and carrier sentence under "think about it while you write" vs "do not think about it while you write". Capture the residual at the carrier cells (the copied sentence in the assistant turn), average within each prompt, then d_l = mean_think(h_l) - mean_dont(h_l) at layers 20-24, u_l = d_l / ||d_l||.

Step s_l = 0.13 ||d_l|| (the stance gap) per dose unit; vector at layer l = k * s_l * u_l, added at the prefix. Dose sweep k = 2-9 peaks at k = 6 (total push ~20 over the five layers).

fit pass@10 0.7843 (from 0.1275), mean log10 rank 1.0412. It works!

Control: random direction per layer (seed 1729, projected onto the top 64 PCs of the read cells) at the same step and dose: no gain. Code: stance_gap.py (capture, direction, sweep).
