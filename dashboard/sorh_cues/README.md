# SoRH cue screen dashboard

Published at https://claude.ai/artifact/AGCkrsx5ETPfuuA65SYMz4 (private to the researcher).

One page per cue in her 11-cue reporting structure, each with the cell names beside the cue number (her numbering
differs from the cells': cue #4 = c3b_*, #5 = c4_*, … #11 = cue10_off vs cue10_on).
- **Single-turn cues #1–#8:**
  - the per-cue conclusions from `notes/sorh_screen_results.md`;
  - a chart per behaviour from agent 10's grid. Each row is a cell against its reference: per-prompt differences, the
    95% interval and the "moves" / "not shown at this n" call, with notes on the 580 rule and the G ceilings;
  - an overview of every reply;
  - the reference and the cue cell side by side, with the full prompt, reasoning and reply, and the judge's cited
    sentences marked.
- **Multi-turn cues #9–#11:** descriptive tables and persist-label bars from `mt_describe.json`, and episodes read turn
  by turn, side by side.
- **Everywhere:** private highlights, and her hand labels with instance marking.

## Charts (since v4: plain count bars)

- **Yes/no measures:** the cell and its reference as k/n bars, with k = `cell_mean × n_prompts` (and `ref_mean × n_prompts`) from
  the grid. This is right only at 1 reply per prompt (the screen). If a stage has more replies per prompt, k must count
  replies or prompts explicitly instead.
- **Numeric measures** (count/share, quality, words): bars for the prompts above and below the reference (`pos`,
  `neg`; ties are neither). The averages and calls are text.
- **Multi-turn:** final-reply bars out of 15 episodes per arm (`final.<measure>` = [k, n] in `mt_describe.json`).
  Per-turn shares stay as a table, because they aren't episode counts.

## Rebuild the data

```bash
git show mats/agent-10-audit:src/sorh_judges.py > <dir>/sorh_judges_a10.py   # agent 10's module, unchanged
.venv/bin/python src/sorh_dash_build.py logs/sorh_ablation/screen/records.jsonl \
    logs/sorh_ablation/screen/analysis/grid.json logs/sorh_ablation/mt/records.jsonl \
    logs/sorh_ablation/mt/analysis/mt_describe.json <dir> <out_dir>
```

This writes `<out_dir>/data/index.json`, `data/cue1.json` … `cue8.json`, and one `data/mt/<arm>.<prompt>.<sample>.json`
per episode. Publish `index.html` with them, about 19 MB in 84 files. The data hold the full texts from `logs/`, so
they stay out of git.

How the data are built:
- Texts are split with `sorh_judges.split_units`, so the judge's sentence numbers line up.
- Judge counts use `sorh_judges.parse_count`.
- The judge's term positions follow parse_count's longest-first rule.

## Database (the `db` capability)

- **Highlights:** private per viewer, `data/users/<id>/hl.<record key>`, body
  `{key, items: [{id, f: "prompt"|"reasoning"|"reply", a: [unit, offset], b: [unit, offset], c: "y"|"b"|"p", t}]}`.
  - Units are `split_units` sentences, 0-based.
  - Record keys are `<prompt_id>.<cell>.<sample>` (screen) or `mt.<arm>.<prompt_id>.<sample>.t<turn>` (multi-turn).
- **Labelling set:** `labelset/screen`, written from `notes/sorh_prereg/labelset_screen_final.json`
  (mats/agent-10-audit 14410c9): 42 entries, seed `20261023|handlabels`, one replacement by rule. The judge stays hidden
  on those replies until her labels are saved.
- **Labels:** `labels/<doc>` for the labelling set, `labels_extra/<doc>` for any other reply.
  - Doc id: `screen.<cell>.<prompt_id>.<sample>`.
  - Body: `stage, cell, prompt_id, row, sample, marked, labeler`, plus
    - `labels {padded, grading, plans_for_score, plans_for_reader, conflict, capability_eval, alignment_eval, hesitates,
      invents_grader (B only), thinned (share prompts only)}`;
    - `instances [{a: [unit, offset], b: [unit, offset], text}]` (her counted items in the reply) and `count` (= the
      number of instances);
    - `count_mode` ("terms"|"items"), `saved_at`, `first_labels {labels, count, instances}` (as first saved, before the
      judge was shown), `first_saved_at`, `edited_after_reveal`, `labelset_seed`, `page_version`.
- **Rules:** `labels`, `labels_extra` and `labelset` are read and written by editors only (`admin`).
