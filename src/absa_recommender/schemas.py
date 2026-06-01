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
