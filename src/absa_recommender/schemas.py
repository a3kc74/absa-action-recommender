from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ABSAAnnotation(BaseModel):
    aspect_expression: str
    aspect_category: str
    opinion_expression: str
    sentiment: str
    model_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ABSAReview(BaseModel):
    review_id: str
    review_text: str
    restaurant_id: Optional[str] = None
    restaurant_name: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    review_time: Optional[datetime] = None
    annotations: list[ABSAAnnotation]


class AspectExtraction(BaseModel):
    extraction_id: str
    review_id: str
    restaurant_id: str
    restaurant_name: Optional[str]
    aspect: str
    aspect_term: str
    opinion_text: str
    sentiment: str
    severity: float = Field(ge=0.0, le=1.0)
    model_confidence: Optional[float]
    review_text: str
    rating: Optional[int]
    review_time: Optional[datetime]


class AspectStats(BaseModel):
    restaurant_id: str
    aspect: str
    mention_count: int
    negative_count: int
    positive_count: int
    neutral_count: int
    avg_severity: float = Field(ge=0.0, le=1.0)
    avg_rating: float
    avg_confidence: float = Field(ge=0.0, le=1.0)
    total_mentions_for_restaurant: int
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None


class AspectRecommendationCandidate(BaseModel):
    restaurant_id: str
    aspect: str
    priority_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: float = Field(ge=0.0, le=1.0)
    mention_count: int
    negative_count: int
    component_scores: dict[str, float]


class SubProblemMatch(BaseModel):
    aspect: str
    sub_problem_id: str
    sub_problem_label: str
    matched_aspect_expression_patterns: list[str]
    matched_opinion_expression_patterns: list[str]
    score: float


class PrototypeMatch(BaseModel):
    aspect: str
    sub_problem_id: str | None
    similarity: float = Field(ge=0.0, le=1.0)
    nearest_prototype_examples: list[dict[str, str]]


class SubProblemPrediction(BaseModel):
    review_id: str
    aspect_category: str
    aspect_expression: str
    opinion_expression: str
    sentiment: str
    model_confidence: Optional[float]
    predicted_sub_problem_id: str
    sub_problem_label: str
    locator_score: float = Field(ge=0.0, le=1.0)
    match_type: str
    needs_review: bool
    matched_patterns: dict[str, list[str]]
    nearest_prototypes: list[dict[str, str]]


class ActionRecommendation(BaseModel):
    aspect: str
    sub_problem_id: str
    actions: list[str]
    kpis: list[str]


class RecommendationItem(BaseModel):
    rank: int
    aspect: str
    sub_problem_id: str
    sub_problem_label: str
    priority_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    severity: float = Field(ge=0.0, le=1.0)
    mention_count: int
    negative_count: int
    opinion_examples: list[str]
    recommended_actions: list[str]
    monitoring_kpis: list[str]
    component_scores: dict[str, float]
    locator_summary: dict[str, int] | None = None


class RecommendationResponse(BaseModel):
    restaurant_id: str
    generated_at: datetime
    recommendations: list[RecommendationItem]
