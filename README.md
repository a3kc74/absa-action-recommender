# ABSA Aspect Priority Engine

Local-first priority scoring for Vietnamese restaurant ABSA outputs.

The project now ranks **Top-N aspects to improve** for a restaurant/month. It no longer detects sub-problems, no longer recommends actions, and no longer uses an action catalog or taxonomy mining workflow.

## Quick Start

```bash
uv run absa-priority validate --input data/samples/absa_outputs.jsonl
uv run absa-priority score-priority --input data/samples/absa_outputs.jsonl --restaurant-id res_demo --top-n 5 --output out/priority.json
uv run streamlit run app/streamlit_app.py
uv run uvicorn absa_recommender.api:app --reload
```

The old `absa-rec` script remains as a compatibility alias for the same CLI app, but the preferred command is `absa-priority`.

## Current Scope

The implemented local prototype keeps:

- ABSA JSONL validation and normalization
- `aspect_category -> aspect`
- `aspect_expression -> aspect_term`
- `opinion_expression -> opinion_text`
- severity scoring
- monthly aggregation by `restaurant_id`, `review_month`, `aspect`
- priority score components
- Top-N aspect ranking
- FastAPI routes
- Streamlit dashboard
- DuckDB schema for future persisted monthly runs
- data/ABSA/scoring monitoring metrics
- source/crawler/peer/trend/benchmark scaffolds for the monthly pipeline

The following old surfaces were removed:

- sub-problem rules and locator
- TF-IDF sub-problem prototype matcher
- action catalog
- action recommendation output
- monitoring KPIs attached to actions
- taxonomy miner/review flow
- feedback endpoint for action recommendations

## Input ABSA Format

Each line is one review JSON object:

```json
{
  "review_id": "rv_001",
  "review_text": "Bàn hơi bẩn nhưng nhân viên thân thiện.",
  "restaurant_id": "res_001",
  "restaurant_name": "Nhà hàng A",
  "rating": 3,
  "review_time": "2026-06-14T10:30:00",
  "review_month": "2026-06",
  "annotations": [
    {
      "aspect_expression": "bàn",
      "aspect_category": "Cleanliness",
      "opinion_expression": "hơi bẩn",
      "sentiment": "negative",
      "model_confidence": 0.91
    }
  ]
}
```

`review_month` is optional. If it is missing and `review_time` exists, the normalizer derives `YYYY-MM`; otherwise it uses `unknown`.

## Output Shape

`generate_priority_ranking(...)` returns:

```json
{
  "restaurant_id": "res_001",
  "restaurant_name": "Nhà hàng A",
  "review_month": "2026-06",
  "generated_at": "2026-07-01T03:30:00Z",
  "top_n": 5,
  "items": [
    {
      "rank": 1,
      "aspect": "Cleanliness",
      "priority_score": 82.4,
      "priority_confidence": 0.78,
      "severity": 0.88,
      "mention_count": 42,
      "negative_count": 25,
      "negative_rate_smoothed": 0.57,
      "mention_share": 0.31,
      "rating_gap": 0.42,
      "trend_score": 0.65,
      "benchmark_gap": 0.48,
      "risk_multiplier": 1.1,
      "component_scores": {
        "negative_rate": 0.57,
        "sentiment_severity": 0.88,
        "mention_share": 0.31,
        "rating_gap": 0.42,
        "trend_score": 0.65,
        "benchmark_gap": 0.48
      },
      "peer_summary": {
        "peer_restaurant_count": 18,
        "peer_negative_rate": 0.22,
        "target_vs_peer_gap": 0.35,
        "peer_support_flag": null
      },
      "trend_summary": {
        "previous_month_priority_score": 61.2,
        "priority_delta": 21.2,
        "negative_rate_delta": 0.19,
        "trend_flag": null
      },
      "opinion_examples": ["bàn hơi bẩn"],
      "data_quality_flags": []
    }
  ]
}
```

There is intentionally no `sub_problem_id`, `recommended_actions`, or `monitoring_kpis`.

## Scoring

The scoring config is in `configs/scoring.yaml`.

Components are normalized to `[0, 1]`:

- `negative_rate`: Bayesian-smoothed negative annotation rate
- `sentiment_severity`: average severity
- `mention_share`: `log1p(mention_count) / log1p(total_mentions_for_restaurant)`
- `rating_gap`: `(5 - avg_rating) / 4`
- `trend_score`: month-over-month negative/severity deterioration when history is supplied
- `benchmark_gap`: target negative rate above peer average when peer data is supplied

The final score is:

```text
priority_score = 100 * clamp(risk_multiplier[aspect] * sum(weight_i * component_i), 0, 1)
```

`priority_confidence` blends support, model, peer, and history confidence according to `configs/scoring.yaml`.

## CLI

Implemented commands:

```bash
uv run absa-priority validate --input data/samples/absa_outputs.jsonl
uv run absa-priority score-priority --input data/samples/absa_outputs.jsonl --restaurant-id res_001 --month 2026-06 --top-n 5
uv run absa-priority run-monthly --input data/samples/absa_outputs.jsonl --restaurant-id res_001 --month 2026-06
uv run absa-priority compute-stats --input data/samples/absa_outputs.jsonl --restaurant-id res_001 --month 2026-06
uv run absa-priority show-labels
```

Source-adapter commands are present as explicit placeholders until a licensed review source is configured:

```bash
uv run absa-priority discover-peers res_001 --radius-meters 1500
uv run absa-priority crawl-month res_001 2026-06
uv run absa-priority infer-absa 2026-06
uv run absa-priority backfill res_001 2026-01 2026-06
```

## Monthly Pipeline Modules

The repository includes deterministic local modules for the design in `Goals.md`:

- `review_normalizer.py`: normalizes raw review dictionaries and hashes normalized review text.
- `dedup.py`: splits unique and duplicate reviews by source review ID or content hash keys.
- `peer_discovery.py`: filters nearby peer restaurants by radius, type, status, and target exclusion.
- `absa_inference.py`: defines an external ABSA adapter protocol and raises clearly when no adapter is configured.
- `benchmark.py`: computes peer aspect monthly summaries from peer stats.
- `trend.py`: computes negative-rate/severity deterioration when previous-month data is available.
- `ranking.py`: sorts priority items and applies the Food Safety Top-3 rule at aspect level.
- `scheduler.py`: provides previous-month scheduling and idempotency key helpers.
- `crawler/monthly.py`: builds local crawl run records.
- `sources/google_maps_adapter.py`: explicit non-scraping adapter placeholder that refuses fetching unless a compliant source is configured.

## API

FastAPI title: `ABSA Aspect Priority Engine`.

Routes:

- `GET /health`
- `GET /api/v1/labels`
- `POST /api/v1/priority/run`
- `POST /api/v1/monthly/run`
- `POST /api/v1/absa/infer`
- `POST /api/v1/crawl/run`
- `GET /api/v1/restaurants/{restaurant_id}/priority?month=2026-06&top_n=5`
- `GET /api/v1/restaurants/{restaurant_id}/dashboard?month=2026-06`
- `GET /api/v1/restaurants/{restaurant_id}/history`
- `GET /api/v1/restaurants/{restaurant_id}/aspects/{aspect}/history`
- `GET /api/v1/restaurants/{restaurant_id}/peer-benchmark?month=2026-06`

The source/crawl/history routes currently return structured placeholder payloads because source adapters and persisted dashboard reads are separate integration work.

## Streamlit Dashboard

Run:

```bash
uv run streamlit run app/streamlit_app.py
```

Tabs:

- Monthly Overview
- Top-N Aspects
- Aspect Detail
- Peer Benchmark
- History
- Data Quality

The dashboard explains why an aspect is prioritized using component scores, negative rate, severity, trend, peer gap, opinion examples, and data quality flags.

## DuckDB Storage

`src/absa_recommender/storage.py` initializes the new monthly priority schema:

- `restaurants`
- `crawl_runs`
- `reviews`
- `absa_annotations`
- `aspect_monthly_stats`
- `peer_aspect_monthly_stats`
- `priority_runs`
- `priority_items`

Helpers currently implemented:

- `init_db(db_path)`
- `save_priority_run(db_path, response, scoring_config_hash, crawl_run_id=None, absa_model_version="unknown")`
- `save_priority_items(db_path, priority_run_id, response)`
- `list_priority_runs(db_path, restaurant_id=None)`
- `get_priority_run(db_path, priority_run_id)`

## Monitoring

`src/absa_recommender/monitoring.py` now tracks data, ABSA, and scoring health:

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

Suggested alerts include crawl success below 90%, peer support below 70%, missing review time above 30%, and low-confidence annotations above 25%.

## Configs

Kept:

- `configs/label_schema.yaml`
- `configs/severity_lexicon.yaml`
- `configs/scoring.yaml`
- `configs/text_normalization.yaml`

Added:

- `configs/crawler.yaml`
- `configs/peer_discovery.yaml`
- `configs/scheduler.yaml`
- `configs/absa_model.yaml`
- `configs/dashboard.yaml`
- `configs/source_policy.yaml`

Removed:

- `configs/subproblem_rules.yaml`
- `configs/subproblem_prototypes.yaml`
- `configs/locator.yaml`
- `configs/action_catalog.yaml`
- `configs/taxonomy_miner.yaml`

## Tests

```bash
uv run pytest
```
