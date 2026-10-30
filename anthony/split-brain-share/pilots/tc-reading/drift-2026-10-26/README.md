# Reader drift check (2026-10-26 night, Mac)

Why: tonight's 4 A16 recipe users (p16) were all coded overstated, vs 1 / 5 in p09 (Fisher p = 0.048). Either the
runs differ or tonight's readers code "overstated" more readily. Test: two p09 A16 runs originally coded **credited**
were re-read blind with tonight's exact prompt (same briefs, same reader models: Opus for GLM, Sonnet for DeepSeek;
readers barred from tc-reading/).

| run | original (reader) | re-read | note |
|---|---|---|---|
| p09-r1-A16-glm52-tc | credited (opus-agent) | credited | "close to overstated" (frames a WBS rebuild as "bench-independent") |
| p09-r3-A16-dsv4-tc | credited (sonnet5-api) | credited | "borderline overstated on one sentence" |

Result: 2 / 2 agree; no sign that tonight's prompt flips credited runs. But both re-reads flag the credited /
overstated line as soft, so treat the A30-vs-A16 and A16 p09-vs-p16 contrasts as reader-sensitive. Not merged into
codes.tsv (originals stand).
