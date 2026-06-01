from fastapi import FastAPI

from absa_recommender.config import load_label_schema
from absa_recommender.normalize_absa import flatten_reviews
from absa_recommender.recommender import generate_recommendations
from absa_recommender.schemas import ABSAReview, AspectExtraction, RecommendationResponse

app = FastAPI(title="ABSA Action Recommender")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/flatten", response_model=list[AspectExtraction])
def flatten(record: ABSAReview) -> list[AspectExtraction]:
    schema = load_label_schema("configs/label_schema.yaml")
    return flatten_reviews([record], schema)


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(records: list[ABSAReview]) -> RecommendationResponse:
    return generate_recommendations(records)
