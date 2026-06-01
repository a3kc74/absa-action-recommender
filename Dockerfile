FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY src ./src
COPY configs ./configs
COPY app ./app
COPY README.md ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "absa_recommender.api:app", "--host", "0.0.0.0", "--port", "8000"]
