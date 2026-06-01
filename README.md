# ABSA Action Recommender

Lightweight local-first repository for an Aspect-to-Action Recommender for Vietnamese restaurant ABSA outputs.

## Local Commands

```bash
uv sync
uv run pytest
uv run absa-rec --help
uv run uvicorn absa_recommender.api:app --reload
uv run streamlit run app/streamlit_app.py
```

## Layout

- `src/absa_recommender/`: Python package with schemas, config loading, ABSA normalization, CLI, and API.
- `configs/`: YAML configs for labels, scoring, severity lexicon, sub-problems, actions, locator, taxonomy mining, and text normalization.
- `data/samples/absa_outputs.jsonl`: Sample Vietnamese restaurant ABSA records using the actual `annotations[]` format.
- `app/streamlit_app.py`: Minimal local Streamlit viewer.
- `tests/`: Smoke tests.

## Current ABSA Format

Input records use `review_text` and `annotations[]`:

```json
{
  "review_id": "rv_001",
  "review_text": "...",
  "restaurant_id": "rest_001",
  "restaurant_name": "Optional name",
  "rating": 2,
  "review_time": "2026-05-30T10:00:00",
  "annotations": [
    {
      "aspect_expression": "phở bò",
      "aspect_category": "Food Quality",
      "opinion_expression": "không hề đậm đà",
      "sentiment": "negative",
      "model_confidence": 0.91
    }
  ]
}
```

Normalization maps fields as follows:

- `aspect_category` -> `aspect`
- `aspect_expression` -> `aspect_term`
- `opinion_expression` -> `opinion_text`

Do not use `evidence` as an internal ABSA annotation field. If a future user-facing response needs examples, prefer `opinion_examples`; any `evidence_examples` field must be sourced from `opinion_expression`.

## Label Schema

Aspect and sentiment labels are loaded from `configs/label_schema.yaml`; do not hardcode aspect labels in core logic.

Current official aspect labels:

- `Food Quality`
- `Food Safety`
- `Service`
- `Price`
- `Cleanliness`
- `Ambience`
- `Location`
- `Menu`
- `Unknown`

Current sentiments:

- `positive`
- `neutral`
- `negative`

Strict validation raises `ValueError` for unknown labels. Permissive validation maps unknown aspects to `Unknown` and unknown sentiments to `neutral`. Aliases such as `food_quality` normalize to canonical labels such as `Food Quality`.

## Normalization Notes

- `src/absa_recommender/schemas.py` contains the Pydantic v2 schemas for the actual ABSA format.
- `src/absa_recommender/normalize_absa.py` loads ABSA JSONL and flattens reviews into one `AspectExtraction` per annotation.
- `AspectExtraction.extraction_id` is deterministic: `f"{review_id}_{annotation_index}"`.
- `severity` is currently set to `0.0`; severity scoring is intentionally deferred.
- Missing `restaurant_id` values are filled with `default_restaurant_id`, which defaults to `unknown`.
- The `/flatten` API endpoint returns flattened `AspectExtraction` records for one submitted review.

Additional running implementation notes are in `implementation-notes.md`.
