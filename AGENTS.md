# AGENTS.md

You are contributing to a lightweight Python data science project named absa-action-recommender.

## Project goal

Build a local-first Aspect-to-Action Recommender for Vietnamese restaurant ABSA outputs.

The system receives ABSA annotations and returns ranked improvement recommendations with:
- aspect
- sub-problem
- priority score
- confidence
- severity
- opinion examples
- recommended actions
- monitoring KPIs
- audit logs
- feedback loop

## Official aspect labels

The official aspect labels are configurable in configs/label_schema.yaml.

Current labels:
- Food Quality
- Food Safety
- Service
- Price
- Cleanliness
- Ambience
- Location
- Menu
- Unknown

Do not hardcode aspect labels in core logic. Load labels from config.

## Input ABSA format

Each input record is JSON:

{
  "review_id": "...",
  "review_text": "...",
  "restaurant_id": "... optional",
  "restaurant_name": "... optional",
  "rating": 1-5 optional",
  "review_time": "... optional",
  "annotations": [
    {
      "aspect_expression": "...",
      "aspect_category": "Food Quality | Food Safety | Service | Price | Cleanliness | Ambience | Location | Menu",
      "opinion_expression": "...",
      "sentiment": "positive | neutral | negative",
      "model_confidence": 0.0-1.0 optional
    }
  ]
}

## Internal naming

Do not use evidence as an internal field name for ABSA annotations.

Use:
- aspect_category -> aspect
- aspect_expression -> aspect_term
- opinion_expression -> opinion_text

If the user-facing output contains evidence_examples, those examples must be sourced from opinion_expression.

Preferred user-facing field:
- opinion_examples

## Sub-problem detection

Sub-problem detection must use:
- aspect_category
- aspect_expression
- opinion_expression

The rule config must use:
- aspect_expression_patterns
- opinion_expression_patterns

Do not use:
- aspect_terms
- opinion_patterns
- evidence_patterns

## Coding rules

- Use Python 3.11+.
- Use uv for dependency management.
- Use Pydantic v2 for schemas.
- Use Polars for batch processing where useful.
- Use DuckDB only for lightweight local persistence.
- Use FastAPI for API.
- Use Typer for CLI.
- Use Streamlit for local dashboard.
- Use pytest for tests.
- Keep configs in YAML.
- Do not require Postgres, Redis, Kafka, Spark, Airflow, Kubernetes, MLflow, or a vector database.
- Keep core logic deterministic and testable.
- Prefer rule-first sub-problem detection before clustering.
- Use prototype matching as a lightweight fallback.
- Use taxonomy mining only to generate suggestions, not to auto-update production configs.
- Every new module must have tests.
- CLI and API must call the same core functions.
- All internal score components must be normalized to [0, 1].
- Final priority_score must be in [0, 100].
- Missing model_confidence should use config default_missing_confidence.
- Unknown labels should be handled according to label_schema.yaml validation mode.