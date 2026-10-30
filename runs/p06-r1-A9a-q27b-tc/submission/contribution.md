# Unspoken-concept steering

**Method.** We build a steering direction from a concept held *unspoken*: resolved from context, never written down. For 20 (description, neutral carrier sentence) pairs I authored — e.g. "the sport played with a shuttlecock" paired with "The committee approved the minutes without changes." — two conditions:

- **Hold**: "Keep in mind {description} as you write. Now write exactly this sentence: '{carrier}'"
- **Suppress**: "Do not try to think of any {category} as you write. Now write exactly this sentence: '{carrier}'"

The concept is never named in either condition; the model must resolve it from the description. Averaging residual states over the carrier-sentence tokens (per prompt, then over pairs) and subtracting layer by layer gives d_ℓ = mean_Hold − mean_Suppress. Varying descriptions, categories and carriers cancel concept identity and carrier content, leaving the mode: an internally resolved, unspoken concept actively held in the workspace while a surface task proceeds. During evaluation we add k·d̂_ℓ·s_ℓ (ℓ = 20–24, fixed per-layer steps s_ℓ ≈ 0.6–0.8, k = 7.4) to the residual stream at all prompt positions, then read with the plain J-lens.

**Why it is new.** Prior contrasts pair contents or behaviours (Turner 2023; Panickssery 2024), transfer a task from examples (Todd 2024), or contrast stances over a *named* concept (Raman 2026). UCS first gives the held concept only by a description, contrasting holding it versus suppressing its *category*. Association items' implied concepts exist in exactly this unspoken, resolved form at the read cell, so UCS pushes the model into the mode the readout needs.

**Evidence** (association fit, 102 items): baseline 0.1275 → **0.7843** strict pass@10; the dose curve peaks sharply at k = 7.4. Controls at the same dose: reversed sign 0.0098; random direction 0.1176; holding without the suppress condition ≤ 0.294.
