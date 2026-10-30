# Night-2 finalists on fresh vs shared answers (steward's card)

Owner j-lens-mean-19c (night-2 C). Offline from existing val readouts; `experiments/c_fresh.py` ->
`out/analysis/fresh/finalists.md`.

**Status** (04:37 BST): done. On the five single-token families (val strict), S20x keeps +0.05 over fam on items whose
answers occur in no other family's fit bank (cos +0.053, rms +0.050); S21 +0.016 / +0.009; S14b +0.016 / +0.012;
knnxs8 +0.025 / +0.012; the label-free S14k and s14t64 are at or below fam there (their gains are on _mt / DM / UM).
**Next**: none (sent to B for finalists-night2.md).

## Why

S20x and S21 put other families' fit targets inside g. Val items whose answers recur among those targets (shared) could
be helped by remembering answers rather than by reading better. Splitting val items by whether any accepted id occurs
among the *other* families' fit targets ("fresh (other)", the S20x-relevant split) or among *any* fit bank's ("fresh
(any)") separates the two. A target-free centre gives the control: any tilt it shows is target frequency, not leakage
(shared-answer items have common target words, which template removal helps).

## Results (val strict, typo / association / basic_readout / multihop / multilingual; 393 items: 321 fresh (other), 72 shared, 274 fresh (any))

| arm | readout | all | fresh (other) | shared (other) | fresh (any) | Δ fam all | Δ fam fresh (other) | Δ fam fresh (any) |
|---|---|---|---|---|---|---|---|---|
| fam@fit | cos | 0.817 | 0.822 | 0.792 | 0.810 | 0 | 0 | 0 |
| s14t64 | cos | 0.784 | 0.773 | 0.833 | 0.748 | -0.033 | -0.050 | -0.062 |
| S14k | cos | 0.812 | 0.801 | 0.861 | 0.781 | -0.005 | -0.022 | -0.029 |
| S14b | cos | 0.840 | 0.838 | 0.847 | 0.821 | +0.023 | +0.016 | +0.011 |
| knnxs8 | cos | 0.845 | 0.847 | 0.833 | 0.836 | +0.028 | +0.025 | +0.026 |
| S20x | cos | 0.883 | 0.875 | 0.917 | 0.865 | +0.066 | +0.053 | +0.055 |
| S21 (early only) | cos | 0.850 | 0.838 | 0.903 | 0.825 | +0.033 | +0.016 | +0.015 |
| fam@fit | rms | 0.809 | 0.810 | 0.806 | 0.796 | 0 | 0 | 0 |
| s14t64 | rms | 0.774 | 0.757 | 0.847 | 0.730 | -0.036 | -0.053 | -0.066 |
| S14k | rms | 0.807 | 0.798 | 0.847 | 0.777 | -0.003 | -0.012 | -0.018 |
| S14b | rms | 0.824 | 0.822 | 0.833 | 0.803 | +0.015 | +0.012 | +0.007 |
| knnxs8 | rms | 0.822 | 0.822 | 0.819 | 0.810 | +0.013 | +0.012 | +0.015 |
| S20x (rms-fitted) | rms | 0.870 | 0.860 | 0.917 | 0.847 | +0.061 | +0.050 | +0.051 |
| S21 (rms-fitted) | rms | 0.835 | 0.819 | 0.903 | 0.803 | +0.025 | +0.009 | +0.007 |

Per family (fresh (other) only) in `out/analysis/fresh/finalists.md`: S20x's fresh gain is on typo (+0.06), association
(+0.04) and multihop (+0.10); S21 loses association (0.69 vs 0.77) and gains typo / multihop.

## Reading
1. **S20x's gain is not remembered answers**: it keeps ~80 % of its all-item gain on fresh items, under both readouts.
2. **S21's single-token gain is mostly on shared items** (+0.033 all, +0.016 fresh, cos), but the target-free S14k shows
   the same tilt (shared +0.07, fresh -0.02): the S14k part carries it; S21's correction itself adds +0.037 fresh over S14k.
3. **The label-free schedule finalists (S14k, s14t64) do not beat fam on the single-token families** (fresh -0.02 /
   -0.05): their val macro gains (+0.032 S14k) come from the _mt families, DM and UM. S14b and knnxs8 are the label-free
   arms that also gain on single-token items (+0.016 / +0.025 fresh, cos).
4. Scope: strict on the single-token families only. The _mt families need the judge (S20: a fitted constant's _mt
   proxy gains do not survive it), and UM / DM strict are not usable for this split.
