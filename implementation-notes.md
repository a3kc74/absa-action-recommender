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

## 2026-06-01: Rule-first sub-problem detection

- Read `AGENTS.md` before coding, as requested.
- Replaced `configs/subproblem_rules.yaml` with valid UTF-8 Vietnamese text. The existing file had mojibake from pasted source material, so rule matching against actual Vietnamese ABSA fields would fail.
- `subproblem.py` only reads `aspect_expression_patterns` and `opinion_expression_patterns`; it does not use the disallowed `aspect_terms`, `opinion_patterns`, or `evidence_patterns` keys.
- Rule matching only considers rules under the same normalized aspect.
- I add `priority / 100` only after at least one aspect or opinion pattern matches. If priority were added to every rule unconditionally, generic fallback could never happen for any aspect that has configured rules.
- `group_extractions_by_subproblem` returns a dictionary keyed by `(restaurant_id, aspect, sub_problem_id)` because the prompt did not prescribe a return shape. This keeps grouping usable for downstream restaurant/aspect recommendations.
- `compute_subproblem_score` returns a `[0, 100]` score by multiplying the parent aspect priority score by a weighted blend of `group_share` and `avg_severity`: `(1 - beta) * group_share + beta * avg_severity`.
- Generic fallback IDs slugify the aspect with underscores, for example `Food Quality` -> `generic_food_quality_issue`.

## 2026-06-01: TF-IDF prototype matcher

- Read `AGENTS.md` before coding, as requested.
- Replaced `configs/subproblem_prototypes.yaml` with valid UTF-8 Vietnamese text. The previous file had mojibake and would not match actual ABSA annotation text reliably.
- Added `PrototypeMatch` to `schemas.py` to make prototype matcher returns stable and validated.
- `prototype_matcher.py` compares only prototypes under the same aspect. If the aspect has no prototypes, it returns `sub_problem_id=None`, `similarity=0.0`, and no nearest examples.
- Matching text follows the requested format exactly: `aspect_expression + " | " + opinion_expression`, normalized with the same `normalize_text` helper used by rule matching.
- The matcher uses `TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))`. Cosine similarity is the sparse dot product because scikit-learn normalizes TF-IDF vectors by default.
- I added a close `muỗng` prototype and a close `món trên menu không còn bán` prototype so the requested tests are deterministic instead of relying on weak similarity to distant examples.
- Prototype similarity is clamped to `[0, 1]` before schema validation because sparse floating-point dot products can produce tiny overshoots such as `1.0000000000000013`.

## 2026-06-01: Sub-problem locator

- Read `AGENTS.md` before coding, as requested.
- Added `SubProblemPrediction` to `schemas.py`. The output uses `aspect_expression` and `opinion_expression` for user-facing prediction records and does not expose any `evidence` field.
- `locate_subproblem` combines rule score, prototype similarity, severity, and model confidence using `configs/locator.yaml`.
- Rule score normalization uses `thresholds.rule_auto_assign`: `normalized_rule_score = min(rule_score / rule_auto_assign, 1.0)`.
- Prototype similarity is used directly because TF-IDF cosine similarity is already in `[0, 1]`.
- Missing `model_confidence` is treated as `0.0` in the locator because `locator.yaml` does not define a default. Upstream aggregation/scoring still uses the scoring config default for aggregate confidence.
- The predicted sub-problem ID is chosen from the stronger of normalized rule score and prototype similarity before threshold decisions. If the final locator score is below `thresholds.needs_review`, the prediction is forced to the generic aspect issue.
- High-risk aspects listed in `locator.yaml` use `thresholds.high_risk_auto_assign` for automatic assignment; other aspects use `thresholds.auto_assign`.

## 2026-06-01: Action catalog mapping

- Read `AGENTS.md` before coding, as requested.
- Replaced `configs/action_catalog.yaml` with valid UTF-8 Vietnamese action text and added generic fallback entries for all 8 official aspects plus `Unknown`.
- Added catalog-facing `ActionRecommendation` to `schemas.py`. The older prototype `models.py` still has a separate `ActionRecommendation` used by the early recommender smoke test; I left that untouched to avoid broad unrelated refactoring.
- `actions.py` lookup only uses `aspect` and `sub_problem_id`. It deliberately does not accept or read `aspect_expression`, `opinion_expression`, or any evidence-like field.
- Fallback order is exact `aspect + sub_problem_id`, then the generic action under the same aspect, then `Unknown.generic_unknown_issue` when the aspect itself is absent.

## 2026-06-01: End-to-end recommendation generation

- Read `AGENTS.md` before coding, as requested.
- Replaced the early prototype `recommender.py` with the actual pipeline over `ABSAReview` and `AspectExtraction`. The old `models.py` remains in the repo for now, but the main recommender path no longer depends on it.
- Restored `data/samples/absa_outputs.jsonl` to valid UTF-8 Vietnamese text so rule/prototype matching can work end to end.
- `generate_recommendations` accepts either reviews or pre-flattened extractions. Empty input returns an empty response.
- The response schema is singular by requirement. For inputs spanning multiple restaurants, `restaurant_id` is set to `"multiple"`; for one restaurant it uses that restaurant ID.
- Aspect-level priority is computed first, then negative extractions for that restaurant/aspect are located to sub-problems. The top sub-problem per aspect is selected using `compute_subproblem_score`.
- `priority_score` on `RecommendationItem` is the selected sub-problem score, not the raw parent aspect score. Parent component scores remain attached for auditability.
- `opinion_examples` are taken from `AspectExtraction.opinion_text`, which came from `opinion_expression`.
- The Food Safety Top-3 rule is implemented conservatively: if a Food Safety recommendation exists and `top_n >= 3`, it is moved into rank 3 when it would otherwise rank lower.

## 2026-06-01: Taxonomy mining

- Read `AGENTS.md` before coding, as requested.
- Added `phrase_miner.py`, `taxonomy_miner.py`, and `taxonomy_review.py` as local-only utilities. They generate review artifacts and do not mutate production configs.
- The miner consumes locator prediction JSONL as dictionaries so it can tolerate future fields. It expects the requested ABSA field names: `aspect_expression`, `opinion_expression`, and `aspect_category`.
- `SubProblemPrediction` does not currently include `severity`, but taxonomy reports need `avg_severity`. The miner reads optional `severity` if present and otherwise defaults missing severity to `0.0`.
- Candidate selection includes negative annotations that are generic, weak by locator score, marked `needs_review`, or high-risk and below the high-risk threshold.
- Clustering uses `TfidfVectorizer(analyzer="char_wb")` with the configured char n-gram range and `AgglomerativeClustering(metric="cosine", linkage="average")`.
- For one candidate in an aspect, the miner emits a single cluster without fitting a clustering model.
- `taxonomy_review.py` is intentionally small: it loads/saves reports and marks human review decisions. It does not apply accepted suggestions to config files.

## 2026-06-01: Typer CLI

- Read `AGENTS.md` before coding, as requested.
- Replaced the initial single-command CLI with explicit commands: `validate`, `recommend`, `inspect-subproblems`, `locate-subproblems`, `mine-taxonomy`, `apply-taxonomy-suggestions`, and `show-labels`.
- `recommend --restaurant-id` overrides `restaurant_id` on all loaded reviews for that command. The prompt usage implies a single target restaurant output even when the sample file contains multiple restaurant IDs.
- `locate-subproblems` adds `severity` to each JSONL prediction payload because taxonomy mining can use it when available, while `SubProblemPrediction` itself stays aligned with the requested locator schema.
- `apply-taxonomy-suggestions` accepts review decisions `approved`, `accept`, or `accepted` and writes only to the requested output path. It never overwrites the original rules file directly.
