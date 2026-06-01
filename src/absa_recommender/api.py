from typing import Any

from fastapi import FastAPI, Query

from absa_recommender.config import load_label_schema, load_yaml
from absa_recommender.normalize_absa import flatten_reviews
from absa_recommender.prototype_matcher import load_subproblem_prototypes
from absa_recommender.recommender import generate_recommendations
from absa_recommender.schemas import (
    ABSAReview,
    FeedbackPayload,
    FeedbackResponse,
    RecommendationResponse,
    SubProblemPrediction,
)
from absa_recommender.subproblem import load_subproblem_rules
from absa_recommender.subproblem_locator import locate_subproblem
from absa_recommender.taxonomy_miner import mine_taxonomy_gaps

app = FastAPI(title="ABSA Action Recommender")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/labels")
def labels() -> dict[str, list[str]]:
    schema = load_label_schema("configs/label_schema.yaml")
    return {
        "aspects": list(schema.get("aspects", [])),
        "sentiments": list(schema.get("sentiments", [])),
    }


@app.post("/api/v1/recommendations/from-absa", response_model=RecommendationResponse)
def recommendations_from_absa(
    records: list[ABSAReview],
    top_n: int = Query(5, ge=1),
) -> RecommendationResponse:
    return generate_recommendations(records, top_n=top_n)


@app.post("/api/v1/subproblems/locate", response_model=list[SubProblemPrediction])
def locate_subproblems(records: list[ABSAReview]) -> list[SubProblemPrediction]:
    schema = load_label_schema("configs/label_schema.yaml")
    rules = load_subproblem_rules("configs/subproblem_rules.yaml")
    prototypes = load_subproblem_prototypes("configs/subproblem_prototypes.yaml")
    locator_config = load_yaml("configs/locator.yaml")
    extractions = flatten_reviews(records, schema, strict=True)
    return [
        locate_subproblem(extraction, rules, prototypes, locator_config)
        for extraction in extractions
        if extraction.sentiment == "negative"
    ]


@app.post("/api/v1/taxonomy/mine")
def mine_taxonomy(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    report, _ = mine_taxonomy_gaps(
        predictions,
        load_subproblem_rules("configs/subproblem_rules.yaml"),
        load_subproblem_prototypes("configs/subproblem_prototypes.yaml"),
        load_yaml("configs/taxonomy_miner.yaml"),
    )
    return report


@app.post(
    "/api/v1/recommendations/{recommendation_id}/feedback",
    response_model=FeedbackResponse,
)
def recommendation_feedback(
    recommendation_id: str,
    payload: FeedbackPayload,
) -> FeedbackResponse:
    return FeedbackResponse(recommendation_id=recommendation_id, **payload.model_dump())
