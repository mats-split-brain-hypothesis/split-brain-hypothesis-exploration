# Reasoning additions to the existing dashboard

This appends a small reasoning section below an existing chart. It preserves the frozen dashboard's layout, navigation, plots, datasets and source citations. It creates no replacement dashboard and makes no network requests. Root alone owns the write to `logs/results_dashboard.html`.

`src/dashboard_original_map.py` writes the exact map to shared `logs/dashboard_reasoning_census/sorh_switch/original_graph_map.json`: 11 IB figures, 15 SoRH figures, section statements, existing example containers, frozen dataset names and authoritative source notes. The site sources are `agent-9-presentation/results_site/site/`; agent7 has equivalent page/assets copies. Using the frozen DATA reproduces IB and SoRH byte-for-byte. The current site data directory has timestamp changes, so it must not silently replace frozen inputs.

## Data contract

The sidecar is one JSON object with `pages`. Only `ib.html` and `sorh.html` are accepted. Each page carries `graphs`, optional `sections`, and a shared `samples` object. A sample can belong to several graphs without duplicating its record in the sidecar.

```json
{
  "pages": {
    "sorh.html": {
      "graphs": {
        "f-switch": {
          "heading": "What the reasoning adds",
          "coverage": {
            "unit": "conversations",
            "total": 420,
            "reviewed": 0,
            "reasoning_unavailable": 0
          },
          "bullets": [],
          "limit": "The census includes the old 3-prompt cohort and the new 20-prompt cohort. No full-review claim is made until all linked trajectory coverage is complete.",
          "sample_ids": []
        }
      },
      "sections": {},
      "samples": {}
    }
  }
}
```

This example contains actual census size but no invented findings. Each source sample entry may contain:

| Field | Meaning |
|---|---|
| `id`, `model`, `prompt_id`, `condition`/`arm`, `draw` | Stable identity and displayed filters |
| `review_status` | `full_read`, `partial_read`, `visible_explanation_only`, or `not_read` |
| `reasoning_availability` | `stored`, `empty`, or `not_stored_by_runner` |
| `analysis`, `bullets` | Concise per-sample interpretation based on the recorded review |
| `prompt` | Exact prompt/intervention text; rendered as text |
| `reasoning_excerpt` | Exact selected reasoning quotation; full reading may cover more than the quotation |
| `explanation` | Retained visible explanation where the probe did not save hidden reasoning |
| `output_excerpt` or `output` | Exact visible output; the UI adds no clipping |
| `limit`, `coverage_note` | Missing content, model judge limits, full/partial span disclosure |
| `source_href`, `source_label` | Local source link and exact locator |

The coverage counts must be computed from the read ledger or completed reviewer results, not from the number of source files collected. `full_read` must mean all available relevant turns were reviewed. A probe with only an 800-character-clipped visible explanation cannot be labeled a full reasoning read. Each graph's `total` has its stated unit; do not add turn records, conversations and probe calls together.

`graphs` keys are existing figure IDs. Insertion defaults to `afterend` of that figure. For a section interpretation, use e.g. `sections.off = {selector: "#off > .section-head", ...}` to insert immediately after its original introduction. Every original statement remains visible. The parent review decides any explicit correction to original claims separately.

The sample browser is native `<details>` plus a text/model filter. It renders 20 matching entries at a time and exposes a Show more button until every attached record is available. It never selects a favourable subset. Each entry can expand to prompt, reasoning/explanation and output. Ordinary content is inserted with `textContent`; source URLs reject unsafe schemes and backslashes.

## Prepare a separate preview

```sh
python3 src/dashboard_inject_reasoning.py \
  --annotations dashboard_annotations/annotation_slots.json \
  --output /private/tmp/results_dashboard.reasoning-preview.html
```

The script refuses to overwrite either its input or the original results dashboard. It only appends marked style/data/script blocks to the two original embedded page strings. Its verification removes each appended block and asserts exact original-page equality, and also verifies every other page is unchanged. The printed report includes original page hashes. Root may integrate the reviewed output after validation.

The bundled templates begin with no interpretations and no invented sample annotations. They are a prepared integration mechanism, not a completed census review.
