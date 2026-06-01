# ABSA Action Recommender

Lightweight local-first repository for an Aspect-to-Action Recommender for Vietnamese restaurant ABSA outputs.

## Local Commands

```bash
uv sync
uv run pytest
uv run pytest tests/test_recommender.py
uv run absa-rec --help
uv run absa-rec validate --input data/samples/absa_outputs.jsonl
uv run absa-rec recommend --input data/samples/absa_outputs.jsonl --restaurant-id res_demo --top-n 5 --output out/recommendations.json
uv run absa-rec inspect-subproblems --input data/samples/absa_outputs.jsonl
uv run absa-rec locate-subproblems --input data/samples/absa_outputs.jsonl --output out/subproblem_predictions.jsonl
uv run absa-rec mine-taxonomy --predictions out/subproblem_predictions.jsonl --output-report out/taxonomy_gap_report.yaml --output-csv out/unmatched_annotations.csv
uv run absa-rec apply-taxonomy-suggestions --reviewed-report out/taxonomy_gap_report.yaml --rules configs/subproblem_rules.yaml --output configs/subproblem_rules.updated.yaml
uv run absa-rec show-labels
uv run absa-rec evaluate --predictions out/recommendations.json --gold data/gold.json --k 5
uv run uvicorn absa_recommender.api:app --reload
uv run streamlit run app/streamlit_app.py
docker compose up api
docker compose up streamlit
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

## Sub-Problem Locator

`src/absa_recommender/subproblem_locator.py` combines rule matching and prototype matching into one prediction record.

`locate_subproblem(extraction, rules, prototypes, locator_config)` returns `SubProblemPrediction` with:

- `review_id`
- `aspect_category`
- `aspect_expression`
- `opinion_expression`
- `sentiment`
- `model_confidence`
- `predicted_sub_problem_id`
- `sub_problem_label`
- `locator_score`
- `match_type`
- `needs_review`
- `matched_patterns`
- `nearest_prototypes`

Locator score:

```text
weights.rule_score * normalized_rule_score
+ weights.prototype_similarity * prototype_similarity
+ weights.severity * severity
+ weights.model_confidence * effective_model_confidence
```

High-risk aspects from `configs/locator.yaml` use the higher `thresholds.high_risk_auto_assign` threshold for automatic assignment. If the final score is below `thresholds.needs_review`, the prediction falls back to `generic_<aspect_slug>_issue` and requires review.

Run `uv run pytest tests/test_subproblem_locator.py` to validate locator behavior directly.

## Action Catalog

`src/absa_recommender/actions.py` maps located sub-problems to operational actions.

Use:

- `load_action_catalog(path)`
- `get_actions(aspect, sub_problem_id, catalog)`

The action catalog lookup only uses:

- `aspect`
- `sub_problem_id`

It must not depend on `aspect_expression`, `opinion_expression`, or any `evidence` field.

Fallback order:

1. Exact `aspect + sub_problem_id`
2. Generic fallback under the same aspect, such as `generic_menu_issue`
3. `Unknown.generic_unknown_issue` if the aspect is not found

`configs/action_catalog.yaml` includes generic fallback actions for all 8 official aspects and `Unknown`.

Run `uv run pytest tests/test_actions.py` to validate action lookup directly.

## End-To-End Recommendations

`generate_recommendations(reviews_or_extractions, top_n=5, config_paths=None, default_restaurant_id="unknown")` runs the local deterministic pipeline:

1. Load configs.
2. Flatten ABSA reviews into `AspectExtraction`.
3. Aggregate aspect stats.
4. Score aspect priority candidates.
5. Locate sub-problems for negative extractions.
6. Select the top sub-problem per aspect.
7. Attach `opinion_examples` from `opinion_text`.
8. Attach catalog actions and KPIs.
9. Sort by `priority_score`.
10. Apply the Food Safety Top-3 rule.
11. Return Top-N recommendations.

`RecommendationResponse.restaurant_id` is the restaurant ID for single-restaurant input. For multi-restaurant batches, it is `"multiple"`.

The API exposes:

- `GET /health`
- `GET /api/v1/labels`
- `POST /api/v1/recommendations/from-absa?top_n=5`
- `POST /api/v1/subproblems/locate`
- `POST /api/v1/taxonomy/mine`
- `POST /api/v1/recommendations/{recommendation_id}/feedback`

Run `uv run pytest tests/test_recommender.py` to validate the end-to-end recommender directly.

Run `uv run pytest tests/test_api.py` to validate API behavior directly.

## Docker

Build and run the FastAPI service:

```bash
docker compose up api
```

Run the Streamlit dashboard:

```bash
docker compose up streamlit
```

Compose mounts `./data` and `./configs` into the containers so local samples and YAML configs remain editable without rebuilding the image.

## Streamlit Dashboard

Run:

```bash
uv run streamlit run app/streamlit_app.py
```

The local dashboard supports:

- JSONL ABSA upload, with bundled sample fallback
- default `restaurant_id` for records where it is missing
- Top-N recommendation generation
- configured label display
- recommendation cards with scores, examples, actions, KPIs, and component scores
- Sub-problem Locator tab with `aspect_category`, `aspect_expression`, `opinion_expression`, predicted sub-problem, locator score, match type, and review flag
- Taxonomy Gaps tab with in-memory weak/generic prediction mining and YAML export

No authentication or database is required.

## DuckDB Storage

`src/absa_recommender/storage.py` provides optional local persistence with DuckDB.

Functions:

- `init_db(db_path)`
- `save_recommendation_run(db_path, response, input_hash, scoring_config_hash, model_version="unknown")`
- `save_recommendation_items(db_path, run_id, response)`
- `save_subproblem_predictions(db_path, predictions, run_id=None)`
- `save_taxonomy_gap_report(db_path, report, run_id=None)`
- `save_feedback(db_path, recommendation_id, implemented, implementation_date, manager_rating, comment)`
- `list_runs(db_path, restaurant_id=None)`
- `get_run(db_path, run_id)`

Tables:

- `recommendation_runs`
- `recommendation_items`
- `subproblem_predictions`
- `taxonomy_gap_reports`
- `feedback`

Run `uv run pytest tests/test_storage.py` to validate storage behavior directly.

## Evaluation

`src/absa_recommender/evaluation.py` provides lightweight offline metrics:

- `recommendation_coverage`
- `subproblem_coverage`
- `generic_subproblem_rate`
- `weak_match_rate`
- `action_coverage`
- `precision_at_k`
- `recall_at_k`
- `ndcg_at_k`
- `stability_score`

Gold format:

```json
{
  "restaurant_id": "res_demo",
  "relevant_sub_problem_ids": [
    "dirty_tableware",
    "bland_or_no_flavor",
    "parking_issue",
    "menu_item_unavailable"
  ]
}
```

CLI:

```bash
uv run absa-rec evaluate --predictions out/recommendations.json --gold data/gold.json --k 5
```

Run `uv run pytest tests/test_evaluation.py` to validate evaluation metrics directly.

## Monitoring

`src/absa_recommender/monitoring.py` provides local monitoring metrics:

- `recommendation_coverage`
- `subproblem_coverage`
- `generic_subproblem_rate`
- `weak_match_rate`
- `action_coverage`
- `avg_locator_score`
- `generic_rate_by_aspect`
- `weak_match_rate_by_aspect`
- `food_safety_unreviewed_count`
- `cleanliness_unreviewed_count`
- `top_unmatched_opinion_phrases`

Use `build_monitoring_snapshot(...)` to compute the full metric set plus suggested alerts.

Suggested alert logic:

- `generic_subproblem_rate > 25%`: run taxonomy miner
- `Menu` generic rate `> 35%`: Menu taxonomy likely lacks rules
- Food Safety weak/generic count `> 0`: review immediately
- Cleanliness weak/generic count above threshold: manual review

Run `uv run pytest tests/test_monitoring.py` to validate monitoring behavior directly.

## Taxonomy Mining

`src/absa_recommender/taxonomy_miner.py` mines weak or unmatched locator predictions for taxonomy review.

Inputs:

- `subproblem_predictions.jsonl`
- `configs/subproblem_rules.yaml`
- `configs/subproblem_prototypes.yaml`
- `configs/taxonomy_miner.yaml`

Candidate selection uses only negative annotations where at least one is true:

- `predicted_sub_problem_id` starts with `generic_`
- `locator_score` is below `candidate_filter.weak_score_threshold`
- `needs_review` is true
- high-risk aspect and `locator_score` is below `candidate_filter.high_risk_score_threshold`

Cluster text is:

```text
aspect_expression + " | " + opinion_expression
```

Outputs:

- `out/taxonomy_gap_report.yaml`
- `out/unmatched_annotations.csv`

The miner does not auto-update production configs. `taxonomy_review.py` only supports loading/saving reports and marking review decisions.

Run `uv run pytest tests/test_taxonomy_miner.py` to validate taxonomy mining directly.

## CLI

The `absa-rec` Typer CLI exposes local workflow commands:

- `validate`: parse ABSA JSONL, validate labels, and print review/annotation counts.
- `recommend`: generate recommendation JSON, save it, and print a top recommendation summary.
- `inspect-subproblems`: print aspect/category text and predicted sub-problem IDs.
- `locate-subproblems`: write negative-annotation locator predictions to JSONL.
- `mine-taxonomy`: generate taxonomy review YAML and unmatched annotation CSV.
- `apply-taxonomy-suggestions`: apply only approved taxonomy report suggestions to a new rules file.
- `show-labels`: print labels loaded from `configs/label_schema.yaml`.

`apply-taxonomy-suggestions` never overwrites the original rules file directly.

Run `uv run pytest tests/test_cli.py` to validate CLI behavior directly.
