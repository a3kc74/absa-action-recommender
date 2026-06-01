# AGENTS.md

You are contributing to a lightweight Python data science project for an Aspect-to-Action Recommender for Vietnamese restaurant ABSA outputs.

## Project goals
- Convert ABSA review annotations into actionable restaurant improvement recommendations.
- Keep the system local-first, testable, and lightweight.
- Prefer deterministic rule-based baselines before ML-heavy components.
- Every feature must include pytest tests.

## Input ABSA format
Each input record is JSON:
{
  "review_id": "...",
  "review_text": "...",
  "restaurant_id": "... optional",
  "rating": 1-5 optional,
  "review_time": "... optional",
  "annotations": [
    {
      "aspect_expression": "...",
      "aspect_category": "Food Quality | Food Safety | Service | Price | Cleanliness | Ambience",
      "opinion_expression": "...",
      "sentiment": "positive | neutral | negative",
      "model_confidence": 0.0-1.0 optional
    }
  ]
}

## Coding rules
- Use Pydantic v2 for schemas.
- Use pure functions in core modules.
- Do not introduce heavy infrastructure.
- Do not require Postgres, Redis, Kafka, Spark, Airflow, Kubernetes, or vector DB.
- Keep configs in YAML.
- Keep all scores normalized to [0, 1] internally and [0, 100] for final priority_score.
- If data is missing, use explicit config defaults.
- Add tests for every new module.
- Make CLI and API call the same core functions.
- Do not hardcode sample-only logic.