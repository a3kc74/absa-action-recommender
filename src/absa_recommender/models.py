from typing import Literal

from pydantic import BaseModel, Field


Sentiment = Literal["positive", "neutral", "negative"]


class AspectOpinion(BaseModel):
    aspect: str
    sentiment: Sentiment
    text: str
    score: float = Field(ge=0.0, le=1.0)


class AbsaOutput(BaseModel):
    review_id: str
    restaurant_id: str
    text: str
    aspects: list[AspectOpinion]


class ActionRecommendation(BaseModel):
    aspect: str
    priority: Literal["low", "medium", "high"]
    action: str
    reason: str
