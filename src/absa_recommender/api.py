from fastapi import FastAPI

from absa_recommender.config import load_label_schema
from absa_recommender.normalize_absa import flatten_reviews
from absa_recommender.schemas import ABSAReview, AspectExtraction

app = FastAPI(title="ABSA Action Recommender")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/flatten", response_model=list[AspectExtraction])
def flatten(record: ABSAReview) -> list[AspectExtraction]:
    schema = load_label_schema("configs/label_schema.yaml")
    return flatten_reviews([record], schema)
