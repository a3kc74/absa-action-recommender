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

- `src/absa_recommender/`: Python package with minimal models, loading, CLI, and API.
- `configs/`: Placeholder YAML files for scoring, severity lexicon, subproblem rules, and action catalog.
- `data/samples/absa_outputs.jsonl`: Sample Vietnamese restaurant ABSA output records.
- `app/streamlit_app.py`: Minimal local Streamlit viewer.
- `tests/`: Smoke tests.
