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
- `src/absa_recommender/aggregation.py` groups flattened extractions into restaurant/aspect-level `AspectStats`.
- `AspectExtraction.extraction_id` is deterministic: `f"{review_id}_{annotation_index}"`.
- `severity` is computed from `opinion_expression` using `configs/severity_lexicon.yaml`.
- Missing `restaurant_id` values are filled with `default_restaurant_id`, which defaults to `unknown`.
- The `/flatten` API endpoint returns flattened `AspectExtraction` records for one submitted review.

Additional running implementation notes are in `implementation-notes.md`.

## Severity Scoring

`src/absa_recommender/severity.py` provides deterministic rule-based severity scoring:

- Base scores come from `configs/severity_lexicon.yaml`.
- `positive` -> `0.0`
- `neutral` -> `0.25`
- `negative` -> `0.75`
- Strong negative patterns raise severity to at least `0.9`.
- Safety patterns, or aspect `Food Safety`, raise severity to at least `0.95`.
- Mild negative patterns without strong/safety patterns score `0.6`.
- Final severity is clamped to `[0, 1]`.

`khó hiểu` is not in `mild_negative_patterns` because unclear menu complaints such as `menu khó hiểu` should remain at least default negative severity for the current tests and product interpretation.

## Aggregation

`aggregate_aspect_stats(extractions, scoring_config)` returns one `AspectStats` record per `(restaurant_id, aspect)` group.

It computes:

- mention, negative, positive, and neutral counts
- average severity
- average rating, replacing missing ratings with `scoring.defaults.rating_if_missing`
- average confidence, replacing missing `model_confidence` with `scoring.confidence.default_missing_confidence`
- total mentions for the restaurant across all aspects
- optional `window_start` and `window_end` from min/max non-null `review_time`

Run `uv run pytest tests/test_aggregation.py` to validate aggregation behavior directly, or `uv run pytest` for the full project suite.

## Scoring Engine

`src/absa_recommender/scoring.py` provides the MVP priority score components:

- `compute_global_negative_rate_by_aspect`
- `smoothed_negative_rate`
- `log_mention_share`
- `normalized_rating_gap`
- `support_confidence`
- `model_confidence`
- `combined_confidence`
- `benchmark_gap`
- `compute_priority_score`

Formula notes:

- `smoothed_negative_rate = (negative_count + alpha * global_mu) / (mention_count + alpha)`
- `log_mention_share = log1p(mention_count) / log1p(total_mentions)`
- `normalized_rating_gap = (5 - avg_rating) / 4`
- `support_confidence = 1 - exp(-mention_count / tau)`
- `combined_confidence = lambda_support * support_confidence + (1 - lambda_support) * model_confidence`
- `benchmark_gap = max(0, neg_rate - peer_avg_neg_rate)`, or `0.0` when peer data is unavailable

For MVP, `trend_score` is expected to be `0.0` when review time is unavailable, and benchmark gap is `0.0` when peer data is unavailable. Risk multipliers come from `configs/scoring.yaml`; missing aspect multipliers fall back to `scoring.defaults.risk_multiplier_if_missing`.

All component functions clamp outputs to `[0, 1]`; final `priority_score` is clamped to `[0, 100]`.

Run `uv run pytest tests/test_scoring.py` to validate scoring directly.

## Sub-Problem Detection

`src/absa_recommender/subproblem.py` implements rule-first sub-problem detection using the actual flattened ABSA fields:

- `aspect` from `aspect_category`
- `aspect_term` from `aspect_expression`
- `opinion_text` from `opinion_expression`

Rules are loaded from `configs/subproblem_rules.yaml`. The supported config keys are:

- `aspect_expression_patterns`
- `opinion_expression_patterns`

Do not use `aspect_terms`, `opinion_patterns`, or `evidence_patterns`.

Rule scoring:

- `+2` for each matched `opinion_expression_pattern`
- `+1` for each matched `aspect_expression_pattern`
- `+ priority / 100` after at least one aspect or opinion pattern matches

Only rules under the same aspect are considered. If no rule scores above zero, the matcher returns `generic_<aspect_slug>_issue` with label `Vấn đề chung về <aspect>`.

`group_extractions_by_subproblem` groups by `(restaurant_id, aspect, sub_problem_id)`. `compute_subproblem_score` returns a `[0, 100]` sub-problem score from the parent aspect priority score, group share, and average severity.

Run `uv run pytest tests/test_subproblem.py` to validate rule matching directly.

## Prototype Matcher

`src/absa_recommender/prototype_matcher.py` provides TF-IDF fallback matching for language variants not covered by rules.

Prototype examples live in `configs/subproblem_prototypes.yaml` and use:

- `aspect_expression`
- `opinion_expression`

Matching text is built as:

```text
aspect_expression + " | " + opinion_expression
```

The matcher uses `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))` and only compares prototypes under the same aspect. It returns the nearest `sub_problem_id`, cosine similarity, and nearest prototype examples.

Run `uv run pytest tests/test_prototype_matcher.py` to validate prototype matching directly.
