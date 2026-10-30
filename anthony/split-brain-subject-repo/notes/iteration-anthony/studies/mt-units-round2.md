# Per-unit reporting of the round-2 survivors on the _mt families (S10's ask)

By j-lens-mean-e1 (night-2 instance B), steward's open-list card; corrected 04:08 BST. Offline: readouts and existing judged
runs, no new judging. Script `experiments/e1_mt_units_table.py` -> `out/analysis/mt-units-round2/table.md`. Val, cos.

**Correction (same night).** The first version divided the judged unit hits by every item instead of the items that have
that unit (bridge2: 9 of 39 multihop_mt items; basic_readout_mt's language: 18 of 48). Its readings 2 and 3 ("the judge
almost never credits bridge2", "basic_readout_mt's judged language unit is flat at 0.31-0.35") were artefacts of that and
are withdrawn. The table below is corrected.

**Readings.**
1. **The language units separate the survivors; the content units barely do.** Concept / readout / correction units sit
   within about 0.1 of each other (proxy concept 0.91-0.94; judged concept 0.68-0.77). The multilingual_mt language unit
   splits them: template removal keeps it (s14t64 / S14k / S21: proxy 0.77-0.85, judged 0.87-0.92), cluster and kNN means
   lose it (knnx8 / knnxs8 proxy 0.30, judged 0.58), S20x and S14b sit between (judged 0.75 / 0.83).
2. **bridge2 is a 9-item unit**: proxy and judge agree in direction (zero 0.67 / 0.44, fam 0.22 / 0.00, S14k 0.67 / 0.22,
   S20x 0.33 / 0.33, S14b 0.56 / 0.56), with the proxy higher; one item moves either by 0.11. Read it as "fam removes the
   second bridge, the template and zero-like centres keep some", not as a precise rate.
3. basic_readout_mt's language unit (18 items) is near ceiling under the judge for every centre (0.83-0.94).
4. **Strict and judged disagree most on S20x and S14b** at the multilingual_mt item level (proxy 0.226 / 0.321, judged
   0.396 / 0.434): their language unit is judged 0.75 / 0.83 but proxy 0.42 / 0.68. For the _mt families, quote the
   judged unit table, not the proxy pass.
5. Judged _mt item means (four families): fam 0.416, s14t64 0.473, S14k 0.461, S14b 0.462, S20x 0.487, S21 0.449,
   knnx8 0.371 (knnxs8 not judged on _mt; its proxy profile equals knnx8's).

## Audit: bridge2 where the proxy credits it and the judge does not (steward's ask; zero, S14k, S20x)

Every such case in the three arms: 7 (2 zero, 4 S14k, 1 S20x; the unit exists for 9 items).

| arm | item (bridge2) | proxy's piece, layer | top 10 (abridged) | judge's summary of the cell | verdict |
|---|---|---|---|---|---|
| zero | 099 (Jules Verne) | " Jules", L56 | Nantes, Bordeaux, Marseille, Château, Sainte, **Jules**, France, Rennes, Loire | "French city and place names ... Jules" | ambiguous: "Jules" sits in a list of places (the answer is Nantes, his birthplace); a first name alone is weak evidence |
| zero | 072 (J. R. R. Tolkien) | " Tolkien", L24 | 作家, **Tolkien**, Britain, Shakespeare, literary, Rowling, Orwell | "English-language literature ... Tolkien, Shakespeare, Rowling, Orwell are named" | **proxy right**: the summary names Tolkien; the judge's form list has only "J. R. R. Tolkien" |
| S14k | 099 (Jules Verne) | " Jules", L56 | Nantes, Bordeaux, Marseille, France, Saint, Château, **Jules**, Paris | "predicting a French city name ... Saint-Jules" | ambiguous, as above |
| S14k | 083 (George Lucas) | " Lucas", L60 | Industrial, Skywalker, industrial, **Lucas**, 工业, Pixar, FX, 特效 | "'Lucas' (Lucasfilm) ... visual-effects industry" | **proxy right**: Lucas is read and named; the judge wants "George Lucas" |
| S14k | 076 (Leonardo da Vinci) | " Leonardo", L36 | 意大利, 威尼斯, 文艺复兴, Italian, Italy, **Leonardo**, frances | "Italy, Venice, the Renaissance ... Leonardo" | **proxy right**: Leonardo with the Renaissance; the judge wants the full name |
| S14k | 072 (J. R. R. Tolkien) | " Tolkien", L24 | 文学, cricket, 作家, **Tolkien**, literary, 读写 | "literature ... English names like Tolkien" | **proxy right** |
| S20x | 072 (J. R. R. Tolkien) | " Tolkien", L24 | **Tolkien**, Sand, Mil, literary, British | "a literary-reference context about J.R.R. Tolkien" | **proxy right**: the summary even writes "J.R.R. Tolkien", which misses the form "J. R. R. Tolkien" on spacing |

**Verdict.** In 5 of 7 cases the bridge is plainly in the readout and in the judge's own summary; the judge misses it
because bridge2's accepted forms are full names ("J. R. R. Tolkien", "George Lucas", "Leonardo da Vinci") and the summary
names the person by surname or with other spacing. The other 2 (" Jules" among French places) are genuinely ambiguous.
So on bridge2 the proxy is closer to right, and the judged multihop_mt numbers undercount: a form-list issue in the bank
(surname-only forms for person bridges), not a lens result. Not fixed tonight (bank data; a note for the user).

## typo_mt (37 reachable items; required: correction)

| arm | proxy correction | proxy pass | Haiku pass | Haiku correction |
|---|---|---|---|---|
| zero | 0.24 | 0.243 | 0.178 | 0.18 |
| fam | 0.38 | 0.378 | 0.511 | 0.51 |
| s14t64 (A) | 0.32 | 0.324 | 0.444 | 0.44 |
| S14k (A) | 0.35 | 0.351 | 0.467 | 0.47 |
| S14b (A) | 0.35 | 0.351 | 0.533 | 0.53 |
| S20x (B, sup.) | 0.38 | 0.378 | 0.578 | 0.58 |
| S21 (B, sup.) | 0.32 | 0.324 | 0.511 | 0.51 |
| knnxs8 (B) | 0.38 | 0.378 | - | - |
| knnx8 | 0.38 | 0.378 | 0.533 | 0.53 |

## multihop_mt (39 reachable items; required: bridge1, bridge2)

| arm | proxy bridge1 | proxy bridge2 | proxy target | proxy pass | Haiku pass | Haiku bridge1 | Haiku bridge2 |
|---|---|---|---|---|---|---|---|
| zero | 0.36 | 0.67 | 0.79 | 0.359 | 0.282 | 0.31 | 0.44 |
| fam | 0.28 | 0.22 | 0.82 | 0.256 | 0.231 | 0.28 | 0.00 |
| s14t64 (A) | 0.41 | 0.67 | 0.82 | 0.385 | 0.308 | 0.33 | 0.44 |
| S14k (A) | 0.41 | 0.67 | 0.82 | 0.385 | 0.282 | 0.31 | 0.22 |
| S14b (A) | 0.36 | 0.56 | 0.82 | 0.359 | 0.256 | 0.31 | 0.56 |
| S20x (B, sup.) | 0.33 | 0.33 | 0.85 | 0.308 | 0.308 | 0.38 | 0.33 |
| S21 (B, sup.) | 0.44 | 0.67 | 0.82 | 0.410 | 0.308 | 0.31 | 0.44 |
| knnxs8 (B) | 0.38 | 0.33 | 0.79 | 0.385 | - | - | - |
| knnx8 | 0.38 | 0.33 | 0.79 | 0.385 | 0.205 | 0.23 | 0.22 |

## basic_readout_mt (48 reachable items; required: language, readout)

| arm | proxy language | proxy readout | proxy pass | Haiku pass | Haiku language | Haiku readout |
|---|---|---|---|---|---|---|
| zero | 0.67 | 0.67 | 0.562 | 0.396 | 0.89 | 0.46 |
| fam | 0.78 | 0.79 | 0.688 | 0.583 | 0.94 | 0.62 |
| s14t64 (A) | 0.89 | 0.83 | 0.708 | 0.688 | 0.89 | 0.75 |
| S14k (A) | 0.89 | 0.83 | 0.708 | 0.604 | 0.94 | 0.69 |
| S14b (A) | 0.89 | 0.83 | 0.708 | 0.625 | 0.94 | 0.71 |
| S20x (B, sup.) | 0.83 | 0.81 | 0.729 | 0.667 | 0.83 | 0.73 |
| S21 (B, sup.) | 0.89 | 0.83 | 0.708 | 0.562 | 0.89 | 0.65 |
| knnxs8 (B) | 0.72 | 0.85 | 0.750 | - | - | - |
| knnx8 | 0.72 | 0.85 | 0.750 | 0.521 | 0.94 | 0.58 |

## multilingual_mt (53 reachable items; required: concept, language)

| arm | proxy concept | proxy language | proxy pass | Haiku pass | Haiku concept | Haiku language |
|---|---|---|---|---|---|---|
| zero | 0.85 | 0.25 | 0.132 | 0.208 | 0.47 | 0.60 |
| fam | 0.91 | 0.62 | 0.340 | 0.340 | 0.68 | 0.79 |
| s14t64 (A) | 0.92 | 0.85 | 0.434 | 0.453 | 0.75 | 0.92 |
| S14k (A) | 0.92 | 0.79 | 0.453 | 0.491 | 0.77 | 0.91 |
| S14b (A) | 0.92 | 0.68 | 0.321 | 0.434 | 0.70 | 0.83 |
| S20x (B, sup.) | 0.91 | 0.42 | 0.226 | 0.396 | 0.75 | 0.75 |
| S21 (B, sup.) | 0.92 | 0.77 | 0.434 | 0.415 | 0.70 | 0.87 |
| knnxs8 (B) | 0.94 | 0.30 | 0.170 | - | - | - |
| knnx8 | 0.94 | 0.30 | 0.170 | 0.226 | 0.77 | 0.58 |


## C's correction (S20, 63d3ea5: piece-proxy _mt gains of the target-fitted constant do not survive Haiku), checked on B's arms

Gain over fam on the four _mt families (val), proxy item pass vs Haiku item pass, from the table above:

| arm | typo_mt proxy / judged | multihop_mt | basic_readout_mt | multilingual_mt | mean of four, proxy / judged |
|---|---|---|---|---|---|
| S20x (s20xt:1) | +0.000 / +0.067 | +0.051 / +0.077 | +0.041 / +0.083 | -0.113 / +0.057 | -0.005 / **+0.071** |
| S21 early-only | -0.054 / +0.000 | +0.154 / +0.077 | +0.021 / -0.021 | +0.094 / +0.075 | +0.054 / **+0.033** |
| (knnx8, for scale) | +0.000 / +0.022 | +0.128 / -0.026 | +0.062 / -0.062 | -0.170 / -0.113 | +0.005 / -0.045 |

Unlike S20's in-family ceiling, **B's arms keep a judged _mt gain**: S20x +0.071 (larger than its proxy, -0.005, which
undercounts its English language-name forms), S21 +0.033 (smaller than its proxy +0.054: multihop_mt's proxy bridge
credit shrinks under the judge). So C's caveat (a correction fitted to the proxy surfaces pieces) does not carry over to
the cross-family average: averaging nine families' corrections removes each one's piece-fitting along with its answer
class (S20x's transfer-matrix insight). Rule kept: quote the judged _mt numbers for every arm.
