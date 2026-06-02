# Implementation Notes

## 2026-06-02: Refactor to ABSA Aspect Priority Engine

This refactor aligns the repository with `Goals.md`: the system is now an aspect priority scorer, not an aspect-to-action recommender.

### Removed surfaces

- Removed sub-problem detection modules:
  - `subproblem.py`
  - `subproblem_locator.py`
  - `prototype_matcher.py`
- Removed action recommendation:
  - `actions.py`
  - `configs/action_catalog.yaml`
- Removed taxonomy mining/review flow:
  - `taxonomy_miner.py`
  - `taxonomy_review.py`
  - `configs/taxonomy_miner.yaml`
- Removed related config files:
  - `configs/subproblem_rules.yaml`
  - `configs/subproblem_prototypes.yaml`
  - `configs/locator.yaml`
- Removed the old prototype `models.py`, which still exposed `ActionRecommendation`.
- Replaced old tests for action/sub-problem/taxonomy with tests for priority ranking, monitoring, storage, API, and CLI.

### Schema changes

- Added `review_month` to `ABSAReview` and `AspectExtraction`.
- `flatten_reviews` derives `review_month` from `review_time` when explicit `review_month` is absent.
- `AspectStats` now includes monthly and component fields:
  - `review_month`
  - `negative_rate_raw`
  - `negative_rate_smoothed`
  - `mention_share`
  - `rating_gap`
- Replaced action recommendation response shape with:
  - `PriorityResponse`
  - `PriorityItem`
  - `PeerSummary`
  - `TrendSummary`
- `PriorityItem` intentionally does not include `sub_problem_id`, `recommended_actions`, or `monitoring_kpis`.

Compatibility aliases `RecommendationResponse = PriorityResponse` and `RecommendationItem = PriorityItem` remain in `schemas.py` only to reduce incidental breakage in type imports. The public pipeline and docs use `PriorityResponse`/`PriorityItem`.

### Priority ranking

- `generate_priority_ranking(...)` is the main pipeline function.
- It accepts ABSA reviews or pre-flattened extractions.
- It aggregates by `(restaurant_id, review_month, aspect)`.
- It returns Top-N aspect items, sorted by `priority_score`.
- It keeps `opinion_examples` sourced from `opinion_expression` through internal `opinion_text`.
- Food Safety can still be forced into Top-3 at the aspect level when configured and above the negative-rate threshold.

Current local behavior:

- `benchmark_gap` is `0.0` unless peer benchmark data is supplied.
- `trend_score` is `0.0` unless previous-month priority/stat data is supplied.
- Missing peer support and missing history are exposed through `data_quality_flags`.

### Scoring config

Updated `configs/scoring.yaml` to match the new design:

- weights:
  - `negative_rate: 0.25`
  - `sentiment_severity: 0.18`
  - `mention_share: 0.12`
  - `rating_gap: 0.12`
  - `trend_score: 0.16`
  - `benchmark_gap: 0.17`
- confidence blend:
  - support/model/peer/history weights
  - `peer_support_tau`
- new `trend`, `benchmark`, and `ranking` sections.

### Added config scaffolds

Added local-first config files for the future monthly pipeline:

- `configs/crawler.yaml`
- `configs/peer_discovery.yaml`
- `configs/scheduler.yaml`
- `configs/absa_model.yaml`
- `configs/dashboard.yaml`
- `configs/source_policy.yaml`

These are scaffolds only. The repository still avoids implementing a Google Maps scraper. Source adapters should respect license/terms restrictions and source-specific retention policy.

### Monthly pipeline helper modules

Added deterministic local modules requested by `Goals.md`:

- `review_normalizer.py` normalizes source review dictionaries and creates text hashes.
- `dedup.py` deduplicates by `source_review_id` first, then source place/text/rating/time keys.
- `peer_discovery.py` filters active nearby peer restaurants without including the target.
- `absa_inference.py` defines an adapter protocol and explicit not-configured exception.
- `benchmark.py` computes peer aspect monthly summaries.
- `trend.py` computes current-vs-previous month trend score and flags insufficient history.
- `ranking.py` ranks `PriorityItem` records and applies the Food Safety Top-3 rule at aspect level.
- `scheduler.py` provides previous-month and priority idempotency helpers.
- `crawler/monthly.py` creates local crawl run records.
- `sources/google_maps_adapter.py` is a non-scraping placeholder that raises unless a compliant source is explicitly enabled.

### API

FastAPI is now titled `ABSA Aspect Priority Engine`.

Implemented routes:

- `GET /health`
- `GET /api/v1/labels`
- `POST /api/v1/priority/run`
- `POST /api/v1/monthly/run`
- `POST /api/v1/absa/infer`
- `POST /api/v1/crawl/run`
- `GET /api/v1/restaurants/{restaurant_id}/priority`
- `GET /api/v1/restaurants/{restaurant_id}/dashboard`
- `GET /api/v1/restaurants/{restaurant_id}/history`
- `GET /api/v1/restaurants/{restaurant_id}/aspects/{aspect}/history`
- `GET /api/v1/restaurants/{restaurant_id}/peer-benchmark`

The crawler/inference/history routes return structured placeholders until a source adapter and persisted dashboard read layer are implemented.

Removed API routes:

- `POST /api/v1/subproblems/locate`
- `POST /api/v1/taxonomy/mine`
- `POST /api/v1/recommendations/{recommendation_id}/feedback`

### CLI

The preferred CLI script is now `absa-priority`. `absa-rec` remains as a compatibility alias.

Implemented commands:

- `validate`
- `score-priority`
- `run-monthly`
- `compute-stats`
- `discover-peers`
- `crawl-month`
- `infer-absa`
- `backfill`
- `show-labels`

Source/crawler/inference commands are explicit placeholders, not fake crawlers.

### Streamlit

Replaced the old recommendation/sub-problem/taxonomy dashboard with aspect-priority tabs:

- Monthly Overview
- Top-N Aspects
- Aspect Detail
- Peer Benchmark
- History
- Data Quality

The dashboard renders component scores, peer/trend fields, opinion examples, and data quality flags.

### DuckDB

Replaced old recommendation/sub-problem/action storage tables with the proposed monthly-priority schema:

- `restaurants`
- `crawl_runs`
- `reviews`
- `absa_annotations`
- `aspect_monthly_stats`
- `peer_aspect_monthly_stats`
- `priority_runs`
- `priority_items`

Implemented helpers:

- `init_db`
- `save_priority_run`
- `save_priority_items`
- `list_priority_runs`
- `get_priority_run`

### Monitoring

Replaced locator/action monitoring with data, ABSA, and scoring health metrics:

- `crawl_success_rate`
- `reviews_fetched_count`
- `new_review_count`
- `duplicate_rate`
- `missing_review_time_rate`
- `absa_inference_failure_rate`
- `low_confidence_annotation_rate`
- `aspect_coverage`
- `peer_support_rate`
- `dashboard_data_freshness`

Alerts are data dictionaries for local dashboard/API use.
