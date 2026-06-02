from typing import Any

from fastapi import FastAPI

from absa_recommender.config import load_label_schema
from absa_recommender.recommender import generate_priority_ranking
from absa_recommender.schemas import ABSAReview, PriorityResponse

app = FastAPI(title="ABSA Aspect Priority Engine")


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


@app.post("/api/v1/priority/run", response_model=PriorityResponse)
def priority_from_absa(
    records: list[ABSAReview],
    top_n: int = 5,
    restaurant_id: str = "unknown",
    month: str | None = None,
) -> PriorityResponse:
    return generate_priority_ranking(
        records,
        top_n=top_n,
        default_restaurant_id=restaurant_id,
        review_month=month,
    )


@app.post("/api/v1/monthly/run", response_model=PriorityResponse)
def monthly_run(
    records: list[ABSAReview],
    top_n: int = 5,
    restaurant_id: str = "unknown",
    month: str | None = None,
) -> PriorityResponse:
    return priority_from_absa(records, top_n=top_n, restaurant_id=restaurant_id, month=month)


@app.post("/api/v1/absa/infer")
def infer_absa(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "not_configured",
        "message": "ABSA inference adapter is intentionally external in this local prototype.",
        "review_count": len(records),
    }


@app.post("/api/v1/crawl/run")
def crawl_run(restaurant_id: str, month: str) -> dict[str, str]:
    return {
        "status": "not_configured",
        "restaurant_id": restaurant_id,
        "review_month": month,
    }


@app.get("/api/v1/restaurants/{restaurant_id}/priority")
def restaurant_priority(
    restaurant_id: str,
    month: str,
    top_n: int = 5,
) -> dict[str, Any]:
    return {
        "restaurant_id": restaurant_id,
        "review_month": month,
        "top_n": top_n,
        "items": [],
        "status": "no_persisted_run",
    }


@app.get("/api/v1/restaurants/{restaurant_id}/dashboard")
def restaurant_dashboard(restaurant_id: str, month: str) -> dict[str, Any]:
    return {
        "restaurant_id": restaurant_id,
        "review_month": month,
        "overview": {},
        "priority": [],
        "peer_benchmark": [],
        "data_quality": {},
    }


@app.get("/api/v1/restaurants/{restaurant_id}/history")
def restaurant_history(restaurant_id: str) -> dict[str, Any]:
    return {"restaurant_id": restaurant_id, "runs": []}


@app.get("/api/v1/restaurants/{restaurant_id}/aspects/{aspect}/history")
def aspect_history(restaurant_id: str, aspect: str) -> dict[str, Any]:
    return {"restaurant_id": restaurant_id, "aspect": aspect, "history": []}


@app.get("/api/v1/restaurants/{restaurant_id}/peer-benchmark")
def peer_benchmark(restaurant_id: str, month: str) -> dict[str, Any]:
    return {"restaurant_id": restaurant_id, "review_month": month, "items": []}
