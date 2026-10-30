# Two-depth contrast steering for the plain J-lens read

The intervention adds two contrast directions to the residual stream, at different depths, at the read token only (position `read`). Both are built entirely from prompts I wrote and from position contrasts; no association target, answer, or item is used anywhere.

**1. Inquiry deflection (layers 4-20).** I capture the residual state of forty self-written scene sentences in two conditions: bare ("She swung the racquet and watched the ball clear the net.") and wrapped as an explicit one-word question ("What activity is being described? Answer in one word. …"). The direction is the mean-state difference between the two conditions. Injected early, it tilts the forward pass toward naming the implied concept instead of continuing the prose, so the top-of-model state carries the answer as its next token.

**2. Continuation-prior deflection (layers 26-30).** The uncentred read J_l h is dominated by a sentence-final continuation prior. I contrast the mean mid-sentence residual with the mean sentence-final residual (an `all`-positions minus `final`-token capture over neutral prose). Adding this direction subtracts the final-position prior while leaving the mid-sentence baseline, exposing the per-item deviation that carries the target.

On association `fit`, the combined vector raises strict pass@10 from 0.1275 to 0.196 and lowers the mean log10 best-target rank from 2.33 to 2.06, applied at scale 1.0.