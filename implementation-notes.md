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
- `absa_inference.py` defines an adapter protocol and a local `PreAnnotatedABSAAdapter`.
- `benchmark.py` computes peer aspect monthly summaries.
- `trend.py` computes current-vs-previous month trend score and flags insufficient history.
- `ranking.py` ranks `PriorityItem` records and applies the Food Safety Top-3 rule at aspect level.
- `scheduler.py` provides previous-month and priority idempotency helpers.
- `crawler/monthly.py` creates local crawl run records.
- `sources/local_jsonl_adapter.py` reads local JSONL records for demo/deployment tests.
- `sources/google_maps_adapter.py` is a non-scraping adapter guard that raises unless a compliant source is explicitly enabled.

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

The crawler and ABSA inference routes remain adapter-oriented; persisted dashboard/priority/history reads are now implemented against DuckDB.

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

`discover-peers` reads persisted peers from DuckDB. `crawl-month` creates a manual `crawl_runs` record for adapter orchestration. `infer-absa` validates a pre-annotated ABSA JSONL through the local ABSA adapter; real model inference remains an external adapter integration.

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

## 2026-06-02: Persisted monthly pipeline and deployment path

Implemented the local end-to-end deployment path proposed after the refactor.

### Monthly pipeline

Added `monthly_pipeline.py` with `run_monthly_from_absa_jsonl(...)` and `run_monthly_from_reviews(...)`.

The persisted pipeline now:

- loads ABSA JSONL or API-provided `ABSAReview` records;
- filters by `review_month`;
- normalizes review rows;
- deduplicates reviews;
- saves `restaurants`;
- creates a `crawl_runs` record;
- saves `reviews`;
- flattens annotations and saves `absa_annotations`;
- computes smoothed `aspect_monthly_stats`;
- computes target-vs-peer `peer_aspect_monthly_stats`;
- reads previous priority rows for trend inputs;
- scores Top-N aspects;
- saves `priority_runs` and `priority_items`.

The idempotency key is `restaurant_id + review_month + scoring_config_hash + absa_model_version`. Without `force=True`, a matching existing priority run is returned instead of creating a duplicate.

### DuckDB storage

Expanded `storage.py` beyond priority snapshots. New helpers include:

- `default_db_path`;
- `save_restaurants`;
- `save_crawl_run`;
- `save_reviews`;
- `save_absa_annotations`;
- `save_aspect_monthly_stats`;
- `save_peer_aspect_monthly_stats`;
- `list_restaurants`;
- `list_review_months`;
- `find_priority_run`;
- `get_latest_priority_response`;
- `get_aspect_monthly_stats`;
- `get_peer_benchmarks`;
- `list_peer_benchmark`;
- `previous_priority_by_aspect`;
- `dashboard_payload`;
- `overview_metrics`;
- `data_quality_metrics`;
- `latest_crawl_run`;
- `aspect_history`.

### API

Updated FastAPI behavior:

- `POST /api/v1/monthly/run` now persists a full monthly run to DuckDB.
- `POST /api/v1/crawl/run` creates a crawl run record with status `created`.
- `GET /api/v1/restaurants/{restaurant_id}/priority` reads the latest persisted priority snapshot.
- `GET /api/v1/restaurants/{restaurant_id}/dashboard` returns persisted overview, priority, peer benchmark and data quality payloads.
- `GET /api/v1/restaurants/{restaurant_id}/history` reads persisted priority runs.
- `GET /api/v1/restaurants/{restaurant_id}/aspects/{aspect}/history` reads persisted aspect priority history.
- `GET /api/v1/restaurants/{restaurant_id}/peer-benchmark` reads persisted peer benchmark rows.

### CLI

`run-monthly` now persists the full local pipeline. Added:

- `--db-path`;
- `--force`;
- `show-dashboard`;
- `list-runs`;
- `aspect-history`.
- `backfill` now runs persisted monthly scoring for each month in an inclusive range and skips months absent from the input JSONL.

Updated adapter-oriented commands:

- `discover-peers` lists persisted peer restaurants from DuckDB.
- `crawl-month` creates a `crawl_runs` row with status `created`.
- `infer-absa` validates ABSA JSONL through `PreAnnotatedABSAAdapter`; real model inference remains external.

README command examples now include comments explaining what each command does.

### Streamlit

Added DuckDB mode:

- sidebar checkbox `Load from DuckDB`;
- DB path input;
- restaurant/month selectors from persisted tables;
- persisted overview, priority, aspect detail, peer benchmark, history and data quality tabs.

Upload mode remains available for ad hoc JSONL testing. Upload mode still computes peer benchmark from multi-restaurant JSONL input by treating `Default restaurant_id` as the target and all other restaurants as peers.

### Docker deployment

Updated `docker-compose.yml`:

- API and Streamlit use `ABSA_DB_PATH=/app/data/local.duckdb`;
- API has a healthcheck;
- added one-shot `monthly-run` service under the `job` profile;
- mounted `./data`, `./configs`, and `./out`.

Updated `Dockerfile` so the local package can be built inside the image by copying `README.md` and `src/` before `uv sync --frozen`.

Added `.env.example` for deploy-time variables.

Added `*.duckdb` and `*.duckdb.wal` to `.gitignore` so local DuckDB runtime files are not accidentally committed.

### Verification

Added `tests/test_monthly_pipeline.py` for the persisted end-to-end path and idempotency. Full verification after this change:

- `uv run pytest`: 64 passed.
- `uv run ruff check .`: all checks passed.
- `docker compose --profile job config`: valid Compose configuration.
- `docker compose build`: API and Streamlit images build successfully.
- `docker compose --profile job run --rm monthly-run`: monthly pipeline job completes and writes `/app/data/local.duckdb` plus `/app/out/priority.json`.
- `docker compose up -d api streamlit`: API and Streamlit start successfully.
- `GET http://localhost:8000/health`: returns `{"status":"ok"}`.
- `GET http://localhost:8000/api/v1/restaurants/res_demo/dashboard?month=2026-06`: returns persisted dashboard data from DuckDB.

## 2026-06-02: Source crawler orchestration and pluggable ABSA adapter stub

Implemented the missing integration surface between raw review ingestion and the persisted monthly priority pipeline.

### Crawler/source path

Expanded `crawler/monthly.py` with:

- `CrawlStrategy`;
- `CrawlResult`;
- `load_crawl_strategy`;
- `crawl_reviews_for_month`;
- `persist_crawl_result`.

The crawler path now:

- reads monthly review rows from a source adapter;
- includes target and peer restaurants from the same source dataset;
- applies per-restaurant review caps;
- normalizes review fields;
- deduplicates with the existing source-id/content key strategy;
- saves `restaurants`, `reviews`, and `crawl_runs` into DuckDB.

`configs/crawler.yaml` now records the intended compliant crawl strategy: source-policy checks, request pacing, retry/backoff, run caps, licensed-source requirement, and explicit no-stealth/no-CAPTCHA-bypass/no-proxy-rotation flags. The implementation intentionally does not add bot-evasion behavior.

### ABSA adapter stub

Added `PlaceholderABSAAdapter` in `absa_inference.py`.

It is a deterministic low-confidence adapter that converts raw review text into the current `ABSAReview` schema. It exists only to prove the pipeline contract and make it easy to replace with a trained model adapter later. The existing `PreAnnotatedABSAAdapter` remains available for already annotated JSONL input.

Added `build_absa_adapter(name)` for adapter selection:

- `preannotated`;
- `placeholder`.

### Full monthly pipeline

Added `run_monthly_from_source(...)` in `monthly_pipeline.py`.

This path runs:

```text
LocalJsonlAdapter
-> crawler strategy / normalize / dedup
-> selected ABSA adapter
-> run_monthly_from_reviews
-> DuckDB priority snapshot
```

### API

Added:

- `POST /api/v1/monthly/run-raw`, which accepts raw review records, runs the selected ABSA adapter, and persists the monthly priority run.

Updated:

- `POST /api/v1/absa/infer` now accepts `adapter_name`, defaulting to `preannotated`.

### CLI

Added:

- `run-full`, which runs local source ingestion, placeholder ABSA inference, persistence, scoring and output export.

Updated:

- `crawl-month --input ...` now crawls from local JSONL and persists restaurants/reviews/crawl_runs; without `--input`, it keeps the manual crawl-run record behavior.
- `infer-absa --adapter preannotated|placeholder` can validate pre-annotated JSONL or run the placeholder ABSA adapter over raw review rows.

### Docker deployment

Updated `docker-compose.yml` so the `monthly-run` job uses `run-full` with `${ABSA_ADAPTER:-placeholder}`. `.env.example` now includes `ABSA_ADAPTER=placeholder`.

### Documentation and tests

Updated README with:

- full local pipeline quick start;
- raw review input shape;
- crawler compliance strategy;
- `run-full`, `crawl-month --input`, and `infer-absa --adapter` commands;
- `/api/v1/monthly/run-raw`.

Added `tests/test_crawler_and_absa_adapters.py` and expanded CLI/API tests for the new source and ABSA adapter path.

Verification after this change:

- `uv run pytest`: 70 passed.
- `uv run ruff check .`: all checks passed.
- `docker compose --profile job config`: valid Compose configuration with `monthly-run` using `run-full --absa-adapter placeholder`.
- `docker compose build`: API and Streamlit images build successfully after the source/ABSA adapter changes.
- `docker compose --profile job build monthly-run`: job image builds successfully.
- `docker compose --profile job run --rm monthly-run`: `run-full` completes in Docker with `placeholder-rule-absa-v0`.
- `docker compose up -d --force-recreate api streamlit`: API and Streamlit start on the rebuilt images.
- `GET http://localhost:8000/health`: returns `{"status":"ok"}` and Docker reports API `healthy`.
- `GET http://localhost:8501`: returns HTTP 200.
- `GET http://localhost:8000/api/v1/restaurants/res_demo/dashboard?month=2026-06`: returns persisted dashboard data from DuckDB generated by the full source-to-placeholder-ABSA path.

## 2026-06-04: Streamlit Google Maps Explore control

Added an interactive Streamlit path for manual exploration from a Google Maps restaurant URL.

### Streamlit

DuckDB mode now shows a sidebar **Google Maps Explore** section before the persisted dashboard selectors. The form accepts:

- restaurant/eatery Google Maps URL;
- crawl month in `YYYY-MM`;
- ward/area name for peer discovery;
- optional/restorable restaurant id, auto-derived from the URL by default;
- Top-N;
- ABSA adapter selection (`placeholder` by default, `trained` optional);
- live/offline Google Maps crawl toggle;
- peer discovery toggle.

Clicking **Run Explore** calls the existing `run_monthly_from_source(...)` pipeline with `source_adapter="google-maps"`, the selected month, area name, and target URL. Successful runs persist into the configured DuckDB path and select the newly processed restaurant/month in the dashboard.

### Idempotency

Before running the pipeline, Streamlit checks `find_priority_run(db_path, restaurant_id, month)`. If a priority run already exists for that restaurant/month, the app skips crawling/scoring and displays the existing run id. The underlying monthly pipeline still keeps its stricter config/model-version idempotency key.

### Documentation

Updated README with:

- Quick Start note for Streamlit Explore;
- current-scope item for URL + month driven Streamlit runs;
- dedicated "Streamlit Google Maps Explore" section describing inputs, idempotency and Docker caveats.

### Deployment note

The existing Docker Compose Streamlit service mounts `./data`, `./configs`, `./models`, and `./.localworkspace`, so the new Streamlit Explore UI can use the same DuckDB file and Google Maps crawler wrapper in the container.
