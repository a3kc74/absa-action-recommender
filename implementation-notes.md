# Implementation Notes

## 2026-06-01: ABSA schema normalization

- Read `AGENTS.md` before coding, as requested.
- The existing project had an early lightweight `models.py` shape using `text` and `aspects`; the requested production input shape is `review_text` plus `annotations[]`. I added the requested schemas in a new `schemas.py` module instead of deleting the older prototype models immediately.
- `data/samples/absa_outputs.jsonl` is being moved to the actual ABSA format so local commands and schema tests exercise the format described in `AGENTS.md`.
- Flattening uses deterministic extraction IDs with zero-based annotation indexes: `f"{review_id}_{annotation_index}"`. The prompt did not specify one-based or zero-based indexing; zero-based matches Python list indexing and keeps the implementation simple.
- `flatten_reviews` receives a loaded label schema instead of reading config internally. This keeps the function deterministic and easier to test.
- `severity` is set to `0.0` exactly as requested. Future severity scoring should replace this in one place during flattening or immediately after flattening.
- Unknown restaurant IDs are filled with the `default_restaurant_id` argument. `restaurant_name`, `rating`, and `review_time` stay optional.
- No internal field named `evidence` is used in the new schemas.
- The CLI reconfigures `stdout` to UTF-8 when supported. This is needed on Windows shells that default to `cp1252`, otherwise Vietnamese sample text can raise `UnicodeEncodeError`.

## 2026-06-01: Severity scoring

- Read `AGENTS.md` before coding, as requested.
- Replaced `configs/severity_lexicon.yaml` with valid UTF-8 Vietnamese patterns. The file previously contained mojibake text from pasted source material, which would prevent direct substring matching for Vietnamese test cases.
- `compute_severity` is rule-based and deterministic. It uses configured `base_scores`, then raises severity for strong negative and safety patterns.
- Mild negative handling is intentionally applied before strong/safety escalation: a negative opinion with a mild pattern and no strong pattern scores `0.6`; strong or safety indicators override that.
- I removed `khó hiểu` from `mild_negative_patterns` because the requested severity tests treat `menu khó hiểu` under `Menu` as at least the default negative severity. This keeps unclear-menu complaints from being downgraded to mild by default.
- `flatten_reviews` now computes severity from `opinion_expression` after label normalization, passing the normalized aspect into severity scoring.
- `flatten_reviews` accepts an optional `severity_config` for tests or callers that want to avoid reading config from disk repeatedly. If omitted, it loads `configs/severity_lexicon.yaml` once per call.

## 2026-06-01: Aggregation layer

- Read `AGENTS.md` before coding, as requested.
- Added `AspectStats` to `schemas.py` because it is a Pydantic schema shared by aggregation callers and future API/CLI layers.
- Implemented aggregation with plain Python grouping. The current logic is small, deterministic, and does not need Polars yet.
- `aggregate_aspect_stats` accepts either the whole loaded `scoring.yaml` structure or its inner `scoring` object. This keeps tests and future callers flexible.
- Missing ratings and model confidence values are replaced per extraction before averaging, using `scoring.defaults.rating_if_missing` and `scoring.confidence.default_missing_confidence`.
- `window_start` and `window_end` were not fully specified. I set them to min/max non-null `review_time` within each restaurant/aspect group, and leave them `None` if the group has no review time.

## 2026-06-01: Scoring engine

- Read `AGENTS.md` before coding, as requested.
- Added `AspectRecommendationCandidate` to `schemas.py` as the Pydantic schema for scored aspect-level candidates.
- Implemented scoring components as small pure functions in `scoring.py`. Each component clamps its output to `[0, 1]`; `compute_priority_score` clamps the final weighted score before converting it to `[0, 100]`.
- Formula choices not specified in the prompt:
  - `log_mention_share = log1p(mention_count) / log1p(total_mentions)`.
  - `normalized_rating_gap = (5 - avg_rating) / 4`, assuming the configured review rating scale is 1 to 5.
  - `support_confidence = 1 - exp(-mention_count / tau)`.
  - `combined_confidence = lambda_support * support_confidence + (1 - lambda_support) * model_confidence`.
  - `benchmark_gap = max(0, neg_rate - peer_avg_neg_rate)`, and returns `0.0` when peer data is unavailable.
- `compute_priority_score` only computes the numeric priority score. Candidate assembly is intentionally left to the recommender layer so sub-problem/action mapping can be added later without coupling it to score math.
- Risk multipliers come from `scoring.risk_multiplier`; missing aspects use `scoring.defaults.risk_multiplier_if_missing`.
