from fastapi import FastAPI

from absa_recommender.models import AbsaOutput, ActionRecommendation
from absa_recommender.recommender import recommend_actions

app = FastAPI(title="ABSA Action Recommender")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/recommend", response_model=list[ActionRecommendation])
def recommend(record: AbsaOutput) -> list[ActionRecommendation]:
    return recommend_actions(record)
