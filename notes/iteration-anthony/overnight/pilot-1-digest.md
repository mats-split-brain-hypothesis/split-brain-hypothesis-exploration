# pilot-1 digest: the first overnight run (2026-10-11)

Steward j-lens-mean-f3. Instances: A = j-lens-mean-c0 [3ef3d9] (clusters and regimes), B = j-lens-mean-cc (matching and
fairness), C = j-lens-mean-ad (depth). Ran 01:20-03:40 BST: every instance finished its direction (plus S2, S5, S10, S11,
S12, opened during the night) by about 03:40, so the steward wound down early instead of keeping an idle pod until 10:30.
**Spend $15.59 of the $30 pilot cap** (judge $12.71, reconciled with OpenRouter's $12.59; pods $2.88: the shared L40S
2.4 h, two short A100 capture runs). All pods terminated; results synced to the Mac; 13 study files in `studies/`.

## Results, in one place

| study | owner | verdict |
|---|---|---|
| S4 (clusters; U3 v1/6) | A | **`knnx8`** (mean of the 8 nearest fit read cells, label-free): +0.05 macro vs fam (val strict), multihop 0.61 -> 0.70; beats fam on every content unit of the _mt families. Costs: the language-name unit (multilingual_mt -0.11 judged); its DM gain does **not** count (same-sentence leak). `kmx64` = fam with no label. kNN, cluster PCA and family PCA estimate one local subspace. Wikitext clusters fail. |
| U4 (J++ vs J-lens) | A | the maps disagree mostly along the family's shared component; centring both with the own-family mean doubles their agreement; J++'s gap sits in the regimes a label-free cluster mean also fixes. |
| U3 v5 | A | closed (see S4.md). |
| U1 (position means) | B | **token matching, not position matching, reads the prompt.** `u1rel` (same offset, any token) is fair on the mention control and gets DM val Haiku 0.57 (zero 0.17, tok 0.79 whose extra is the leak); `u1endcar` 0.64 is the best fair DM centre; val macro = tok's. A bench registration of u1rel / u1endcar is written, its judged half left for the day. |
| S8 (tightness dial) | B | no fair setting beats the position mean by more than noise; every step of tightening that adds DM passes adds mention leak. `s8knn32` +0.030 vs fam (val), guardrail ok. The useful form is kNN restricted to other sentences. |
| S11 (UM mention control) | B | **UM pass@10 cannot validate a centre**: the lens surfaces an attribute more when the sentence is quoted about a colleague (0.97) than self-described (0.70), for every centre. |
| S5 (category-word g) | B | null as a method; as a diagnostic it confirms S10 causally (the language-name direction alone moves the language unit 0.17 <-> 0.96). |
| S6 (multihop) | C | both multihop banks score the bridge; knnx8 / pco16 lift it by pushing the final answer down; every centre removes multihop_mt's second bridge (0.67 -> 0.22 under fam). |
| S7 (subspace removal) | C | `pco16` +0.039 (cos) / +0.027 (rms) vs fam on val strict, fair, but fails the judged multilingual_mt guardrail (language unit). Not registered. |
| S9, S3, S12 | C | negative: g built from the item's own states (S3, S9) removes its own content; same-token-other-content (S12) is fair but weak. |
| S10 (multilingual_mt guardrail) | C | **"a mean over cells that share X removes X"**: matched centres lose the language-name unit, not the concept; a same-language mean reproduces it, an other-language mean does not. |
| S2 (neutral fills) | C | = fam where fam's gain is the template prior (association, multilingual_mt); spares part of multihop_mt's bridge; loses typo, where removing the shared misspelling is right. |

**The night's two big lessons.** (1) Fairness has to be tested where the centre can actually match on context:
several apparent wins (tok and knnx8 on DM, every UM gain) are prompt reading, and the mention control only bites when
the references contain the probe's own carriers (now a rule in research-loop.md). (2) What a mean removes is whatever
its reference cells share: the template prior (good), the family's category (bad for multihop's bridge) or the
language name (bad for multilingual_mt's required unit). That is the lens for the next round of g's.

## Decisions for the user

1. **UM in the headline?** S11 shows UM pass@10 rewards prompt reading; keep it as a guardrail only?
2. **Per-unit reporting for the _mt families?** The multilingual_mt "guardrail" is the language-name unit (S10).
   Report concept and language units separately, and decide whether subtracting the language name is a harm.
3. **Bench reads.** B read the bench once for its registered `u1rel` / `u1endcar` comparison (strict; U1.md); the judged
   half is queued for a day session. Approve finalists for registration: `knnx8` (S4b, bigger dev split), `u1endcar`,
   `s8knn32`?
4. **U2 / S2.** B judged U2's per-item rewrites unnecessary after the neutral-context counterfactual also read the prompt;
   C's hand-written S2 fills gave no finalist. Close U2, or still run it?
5. **U3 variants 2-4** still need your call on the "J++ is a comparison, never a centre's lens" rule.
6. **OpenRouter key:** [amount] left of its $100 cap; top up before a $45 night.

## What to change in the process (for the next night)

- Budget UM judging separately (about $3 per arm at 4 layers; DM $0.85) and estimate from a `limit=3` dry run; log what a
  judge run reports, never a key delta (it double-counted once).
- `git status` before every commit, never `git add -A` (the out symlink incident).
- The instances finished in about 2.5 h of a 9 h window: give each a longer backlog (second-wave cards per direction), or launch
  fewer instances with more cards each. A steward that can open new cards for idle instances worked well (S2, S5).
- Timestamps written into study files by instances drifted ahead of the clock (C: "06:35" at 03:40); use `date`, and
  treat commit times as the record.
- Cross-instance checking was the most valuable thing the setup did: B's caveat corrected A's DM claim within the hour.

## Night log

## Incidents

- **00:31 UTC, the Mac's out/ was wiped.** C committed its worktree's `out` symlink (`git add -A`; `.gitignore` had
  `out/`, which matches directories only); landing it fast-forwarded the main checkout and git replaced the ignored
  out/ directory with the symlink. Root cause on my side: the preamble told instances to make that symlink without
  warning against committing it. A caught it within minutes and landed the git fix (72ab096: untrack, ignore `out`);
  I restored out/ from the volume (captures, eval with every judged run, analysis, lens caches; 6 minutes) and fixed
  the preamble (1196f21) and research-loop pitfalls (cafa012). Lost: only A's first U4 battery output (regenerable).
- **Name clash:** two sessions are called j-lens-mean-c0 (instance A and an old idle one); messages to A need the ref.
- **Budget accounting gap:** running pods were invisible to `board.py check` (cost logged at terminate only); fixed at
  00:29 (1481cc2).

## Results as they arrived

- **01:58 BST, B (U1), fairness:** on umot's mention control, position-only matching (`u1rel`) is selective (held 0.78
  vs mentioned 0.23), while every token-keyed centre leaks the mention (tok 0.82 / 0.59; carpos 0.95 / 0.91). DM val,
  Haiku: u1rel 0.57, tok 0.79, zero 0.17. So part of tok's DM gain is reading the prompt. The neutral-context
  counterfactual (same sentence without the concept) also reads the prompt (0.94 / 0.81); B judged U2 / S2 captures
  unnecessary on that basis (a decision for the user to review). Generic script: `experiments/u1_mention.py --arms`;
  forwarded to A and C for their context-built centres.
- **02:3x BST, A (S4), a label-free, context-matched centre (fairness on DM: see the correction below):** `knnx8` (mean of the 8 nearest fit read
  cells, any family) is fair on the mention control (held 0.79 / mentioned 0.12; tok 0.82 / 0.59) and +0.05 macro vs
  fam on val strict (multihop 0.61 -> 0.70). Haiku on UM / DM pending. Forwarded to B (S8's dial) and C (S6).
- **Budget pacing (02:20):** $3.7 spent; pod ~$10 by morning; A's S4 Haiku ~$7.6 agreed as its last judging tonight;
  B + C share ~$9 of judging.
- **02:25 BST, A (S4) judged:** knnx8 on DM val (Haiku, 4 layers) 0.79 = tok 0.79 (zero 0.17); UM 1.00 vs zero 0.885.
  **Corrected 02:4x (A, after B's caveat): the DM number is not cleared as fair.** On DM val 53-75 % of mid-sentence
  cells' 8 neighbours share the item's carrier sentence (fit and val share carriers; the mention-control bank does
  not, so its clean result does not transfer). B's `s8knn8xs` (neighbours from other carriers) is the test. UM,
  multihop and the macro gain are unaffected. A's judging totalled $9.63 (over its $7.6 estimate: DM was
  $0.85 per arm, UM about $3); A has stopped judging for the night.
- **Budget, 02:27:** $14.3 spent; the pod adds about $8.7 by 10:30, so judging has about [amount] left for the night;
  B and C asked to keep to <= $3 each. Lesson for the next night: UM judging (about $3 per arm at 4 layers) needs its
  own line in the budget plan, and estimates should come from a `limit=3` dry run, not a guess.
- **Process rule added (from B, 02:5x):** a mention-control pass counts only if the centre's references contain the
  probe items' own carriers (research-loop.md, "Controls"). B's judge spend $3.49, no more planned.
- **Ledger double count fixed (02:5x):** A logged judge spend as "OpenRouter key delta", which on the shared key
  included B's calls; the ledger said $13.12 of judging against OpenRouter's $10.73 for the day. A -$2.39 correction is
  in the ledger. Rule for next time: log what the judge run reports (or its own call count x price), never a key delta.
  The OpenRouter key has $49.07 of its $100 cap left: top it up before a $45 night.
- **03:0x, B (S8), kNN fairness inside the evaluation banks:** plain kNN within the position key leaks the mention
  more as k falls (mentioned 0.59 at k = 4, 0.36 at k = 8); kNN restricted to other sentences stays fair (0.22-0.28).
  `out/analysis/S8/mention-knn`. A's knnx8 always uses the dev-fit pool, so its fairness on DM rests on this. B's job
  `mc-knnx8` looked dead on the pod: B had stopped it on purpose; `podrun.sh stop` now leaves a marker.
- **03:1x, C (S10), the multilingual_mt guardrail explained:** the losses of matched centres (tok, knnx8, pco16) are
  on the bench's required "language" unit (the prompt's language named: " Indonesian", " Arabic"), not on the
  concept: references that share the item's language subtract its name. On the concept unit pco16 / knnx8 >= fam (L52
  0.62 / 0.58 vs 0.51). So the guardrail measures something closer to "is the language subtracted" than a harm to the
  readout of the concept; for the user: should the _mt families be reported per unit? (studies/S10.md)
- **03:2x, A (S4), the _mt families per unit** (`out/analysis/S4/extra/mt-units.md`): knnx8 >= fam on every content unit
  (concept 0.94 vs 0.91, readout 0.85 vs 0.79, multihop bridge1 0.38 vs 0.28) and loses only language-name units
  (multilingual_mt 0.30 vs 0.62, basic_readout_mt 0.72 vs 0.78). **Every centre removes multihop_mt's bridge2** (zero
  0.67 -> fam 0.22): forwarded to C as the likely S6 mechanism.
- **03:3x, A's verdict on knnx8 on DM:** the DM gain does not count. Its mid-sentence DM val passes (21) equal tok's
  (21) and are the same-sentence leak (B's fair, other-sentence kNN gets 8-10); its sentence-final "." passes (17 vs
  tok 15) are the defensible part. The fair DM kNN is B's `s8knn8xs`. knnx8's UM, multihop and content-unit gains stand.
- **03:2x, B (S11), user_modeling cannot validate a centre:** with a new 27B capture (~90 renders; capture pod $0.2,
  terminated), the user's self-description vs the same sentence quoted about a colleague: the plain lens surfaces the
  attribute *more* for the quote (0.97 vs 0.70), and every centre does the same. UM readouts carry the prompt's attribute
  content regardless of attribution, so UM pass@10 cannot separate user modelling from reading the prompt
  (studies/S11.md). knnx8's UM 1.00 is therefore not evidence for it; A asked to qualify S4. A question for the user:
  keep UM in the macro headline?
- **03:3x, B done (U1, S8, S11):** token matching, not position matching, is what reads the prompt. The fair position
  mean `u1rel` (= fam on single-cell families) gets DM val Haiku 0.57, `u1endcar` 0.64, against tok's prompt-reading
  0.79; val macro equals tok's. On the bench, where items share no carriers, tok's DM lead vanishes, as B had registered
  (a registered bench read; see U1.md). S8: tighter matching buys DM passes only with mention leak. Next (day session):
  the judged half of the U1 bench registration. B judge spend $4.34 (ledger); idle with an hourly heartbeat.
- **03:1x BST, C done (S6, S9, S3, S7, S10, S12):** "a mean over cells that share X removes X": on multihop_mt the family
  mean holds (and removes) the bridge's category; on multilingual_mt tok / knnx8 / pco16 lose the language-name unit, not
  the concept. pco16: val strict +0.039 vs fam, fair on the mention control, but judged multilingual_mt -0.11. Any g
  built from the item's own states (S3, S9) removes its content. C judge spend $1.13.
- **03:15 BST, steward:** with B and C done and 7 h left (about $7 beyond the pod), offered C its own next card S2 (neutral
  fills that vary the shared category / language; cap $3) and B the S5 card (subtract the category word's state; cap $2),
  sharing one capture pod. Both optional.
- **03:20 BST, captures for S5 (B) and S2 (C)** shared one A100 capture pod (about 10 minutes, terminated); C's job queued
  behind B's with NEED_GB=60, since two 27B loads do not fit on 80 GB.
- **03:4x BST, C done with S2 (neutral fills; studies/S2.md):** hand-written neutral fills equal fam on association and
  multilingual_mt, so fam's gain there is the template prior and needs no data; they spare multihop_mt's bridge at
  mid depth (val 0.31 vs fam 0.26, matched control 0.23) but not at L52-60; they lose typo (0.75 vs 0.92: the
  misspelling shared by the family's prompts is the target's rival, so a mean that removes it is right). No finalist.
- **03:5x BST, B done with S5 (category-word g; studies/S5.md):** null as a method (+0.003 vs fam on fit; random and
  other-category words do as well; the UM gain from adding "person / user" back is a bias, 0.30 pass on the
  information-free S11 prompts). As a diagnostic it confirms S10 causally: the item's language-name word direction alone
  moves multilingual_mt's language unit 0.56 -> 0.96 when added back, 0.17 when removed, concept unit flat (val item
  pass 0.34 -> 0.49). It uses a target unit, so it is not a method.
