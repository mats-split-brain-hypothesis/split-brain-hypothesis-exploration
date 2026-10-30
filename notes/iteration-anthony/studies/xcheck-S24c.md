# Blind cross-check of C's S24c flip classes (A, j-lens-mean-2e, night-2, 06:23 BST; steward's card)

Sample: 30 val2 flips from `out/analysis/S24/flips-val2.json`: all 26 whose fam rank is above 50 (the judged classes a / b / c;
14 distinct item-layers across the four arms) plus 4 random a0 (rank 11-50). I classified the judged ones from fam's decoded
top 50 (byte-level tokens decoded to UTF-8) before opening C's labels (`flips-classes.json`, studies/S24.md "S24c"), with C's
definitions: a = the concept in fam's top 50 only in another script / language; b = only as a near-miss form; c = absent.

| item-layer (target) | mine | C | note |
|---|---|---|---|
| v2-as-v-007 L24 (hunting) | a | a | 狩猎 / 猎 / chasse |
| v2-mh-v-053 L24 (dog) | b | b | " dogs" |
| v2-as-w-059 L44 (surprise) | **c** | **a** | fam has 意外 "unexpected", 突然 "sudden"; no 惊喜 / surprise |
| Hercules L48, Pluto L56 / L60, patience L48 / L40, Pumpkin L56, Jenner L36, hair L24, pear L20, Shakespeare L32, Tyson L24 | c | c | no translation or form in fam's top 50 |
| 4 random rank 11-50 flips | a0 | a0 | mechanical |

Agreement: 13 of 14 judged item-layers (93 %), all a0. The one disagreement is systematic in kind: C counts a broader or
neighbouring concept in another language (意外 "unexpected" for *surprise*) as (a); I count only a translation of the
target. Under my reading S14b-x's absent share is 5 / 21 = 24 % (C: 19 %), S14b's 24 % -> 29 %; the ordering of the arms
and C's reading ("most of the gain is re-ranking what fam already reads") are unchanged.
