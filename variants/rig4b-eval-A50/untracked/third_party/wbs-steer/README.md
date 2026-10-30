# wbs-steer

Reference implementation of **white-bear steering (WBS)** from

> Priya Raman, Tomasz Wierzbicki, Elise Fournier. *White-Bear Steering: Steering Toward a "Think About It" Stance
> Makes Implied Concepts Readable in J-Space.* Preprint, Orrery Lab, October 2026.

The white-bear direction is the mean residual difference between prompts that tell the model to **think about** a
concept while it copies a sentence and prompts that tell it **not to think about** the same concept, same concept
and same sentence (WorkspaceBench `directed_modulation` pairs). Adding it at mid depth, at a large dose, makes
implied concepts more readable through the plain J-lens. See the paper for the method, the dose curve and the
controls.

Version 0.1.0 (the code behind the paper's §3). MIT licence (`LICENSE`).

## Use

```python
from wbs_steer import load_pairs, white_bear_direction, steering_vectors

pairs = load_pairs("evals/directed_modulation/items.json")   # 35 think / don't-think pairs
u = white_bear_direction(capture, layers=range(40, 49), pairs=pairs)
vectors = steering_vectors(u, dose=6.0, step=step_per_layer)   # {layer: tensor}, add at the prefix positions
```

`capture` is any function that takes a capture spec (`{"layers": [...], "prompts": [{"user", "assistant"}],
"positions": "assistant"}`) and returns `{"mean": {layer: tensor[d_model]}}`: the residual means over the tokens of
the copied sentence, for your model. The paper's band (layers 40-48) and steps (Table A1) are for Qwen3.6-27B; for
another model, pick the band where the J-lens readout of `u_l` first reads as a stance (§6.1) and set `step` to about
1.25 % of the median residual norm at each layer.

## Citation

If you use wbs-steer or the white-bear direction, please cite the paper:

```bibtex
@article{raman2026whitebear,
  title   = {White-Bear Steering: Steering Toward a ``Think About It'' Stance Makes Implied Concepts Readable in J-Space},
  author  = {Raman, Priya and Wierzbicki, Tomasz and Fournier, Elise},
  journal = {Preprint, Orrery Lab},
  year    = {2026}
}
```
