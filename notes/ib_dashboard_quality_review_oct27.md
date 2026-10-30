# IB dashboard quality review, 27 October

Read-only review of agent17's `notes/reasoning_review_observations.json`, `research_dashboard/editorial.json`, and `src/build_research_dashboard.py`. No raw reasoning bulk read or model calls. Root's quoted observations and explicitly described reading scope are treated as the case evidence; their private causal interpretation is not independently re-established here.

## Substantive edits for root

1. **STOP/detector report category is conditional.** `reported_broken_test` means no submitted hack composite **and** a supported visible flaw report. `stop3_outcomes.py`:5–13 makes it category2 after excluding category1. Hack episodes were not all sent to the report judge. A detector0/6 cannot establish no recognition or no disclosure. Renamed the catalog chart to “No submitted hack and a supported visible flaw report”; corrected its endpoint definition in both derived artifacts.
2. **Do not rule out capability from one ordinary-code excerpt.** Observations:368 says DeepSeek's lower chat outcome “cannot be reduced to insufficient capability.” The selected excerpt and final code do not rule out capability/time constraints as contributors to the aggregate. Suggested replacement: “These excerpts do not establish which of capability, time, objective interpretation or setting belief explains DeepSeek's lower aggregate outcome.” The Qwen equality exploit does establish that tools are not necessary for every hack.
3. **Update the artifact-inspection limit.** Observations:221 still says the exact test write needs linking. Root has subsequently inspected operation59; the scope statement should list it and remove the stale caveat.
4. **Separate intention from proved semantic correctness.** In `late_update_is_interpreted_through_history`, “specification-directed/ordinary algorithm” is safer than “honest algorithm” unless the final code was independently checked. A failing contradictory suite alone does not certify an honest artifact. This differs from the AISI pilot, which has manual artifact review and a semantic oracle.
5. **Provider context.** Editorial:33 should include Parasail FP8 for current Qwen27 chat. DeepInfra BF16 describes its current harness runs, not all current behavior.
6. **Authorized versus unauthorized checker repair.** Editorial:151's “repaired tests restore a permitted route” should specify investigator-authorized repair in the AISI intervention. DeepSeek's own forbidden test edit is not a permitted route merely because it repairs an incorrect expectation.
7. **Narrow subclaim4.** Editorial:60 is already qualified to task proxies, but the precise result is conditional task-proxy pursuit. It does not identify evaluation cues as the unique trigger of reward seeking. “Models often stop” should not collapse some already-working late states that remain hacked with early states that never begin.

Other current IB observations explicitly distinguish selected cases, excerpts, expressed reasoning, disclosure and hidden intent. Those limits are appropriate. Their aggregate mechanism frequency remains unknown.

## Catalog changes completed

The revised catalog retains41 stable findings and all45 frozen current cells. It now has28 binomial charts and26 descriptive tables with an equivalent plain-text `evidence` field. No numeric source observations were discarded.

Converted to descriptive counts: overlapping rejection/tool windows, selected judge remarks, release-case persistence and timing, hypothetical first-report truncations, mixed pooled micro-pilots, one-draw file/case observations, cross-benchmark screen summaries, and repeated branch probes. Current missing-output lower bounds and incomplete cumulative rejection trajectories also no longer receive generic independent-binomial confidence bars. These counts remain useful, but the displayed denominator should not imply independent task samples or turn missing continuations into negative outcomes.

Remaining Wilson intervals are explicitly descriptive cell intervals. Repeated draws on selected tasks and paired source prefixes still limit population inference; they are not confidence intervals for paired treatment differences. AISI's chart is “Confirmed specification-violating artifact,” six behavioral cells with one draw each; its816 oracle calls stay measurement metadata. Authority has zero valid completed windows and no behavioral chart. Unchecked cooperation labels remain excluded from charts. Duplicate run4 points to the current Qwen-before result rather than adding another plot.

Every finding now has a distinct, family-specific implication and a concrete discriminating contrast. These are proposed questions, not authorizations or plans to run new experiments.

## Costs

Current STOP/detector totals now cite A4 notes:4185 and the raw per-call `usage.cost` ledger: Qwen$18.08, DeepSeek$8.75, GLM$7.38, Qwen27$4.80. Each total covers **all three arms together**, so it must not be charged separately to the two charts. The same note records run4's two Qwen arms$14.62 and Qwen27-before$4.90.

Chat source-note provider totals: Qwen$4.42, DeepSeek SiliconFlow$4.01, DeepSeek Novita$2.47, GLM$1.89, Qwen27 Parasail$2.43, with exact note references. Two Qwen in-flight calls are outside its recorded total. These totals were not independently recomputed here and do not include every preflight, judge, or discarded provider attempt. Exact late subsets, homework and rejection costs remain explicitly unknown with ledger locators. No additive grand total is claimed.

## Builder review

The builder preserves raw statuses separately, makes selected-case reading limits visible, validates quoted substrings against records, and separates source/result audits from direct reasoning cases. No arithmetic is performed there beyond coverage counts, so the statistical risk is the downstream chart renderer applying Wilson intervals indiscriminately. The revised catalog avoids the problematic cases.

The current builder can display the converted counts through its existing `evidence` field. If it adds table rendering, `descriptiveTables` should receive no CI or percentage interpretation and its sources can be normalized with the existing `source_link` helper. Overrides are applied after normalization; any override that introduces new charts or local source paths should be normalized again. At this review point `overrides.json` had not yet been written, so no claim of a completed end-to-end build is made.

Validation: all catalog IDs unique;41 distinct hypothesis implications and next questions; every k/n satisfies0≤k≤n; source-manifest hashes unchanged. No parent files edited.
