import json
from pathlib import Path

from absa_recommender.api import (
    health,
    labels,
    locate_subproblems,
    mine_taxonomy,
    recommendation_feedback,
    recommendations_from_absa,
)
from absa_recommender.schemas import ABSAReview, FeedbackPayload


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


def test_health_works() -> None:
    assert health() == {"status": "ok"}


def test_labels_include_location_and_menu() -> None:
    payload = labels()

    assert "Location" in payload["aspects"]
    assert "Menu" in payload["aspects"]


def test_recommendations_from_absa_returns_recommendations() -> None:
    response = recommendations_from_absa(_sample_reviews(), top_n=5)

    assert response.recommendations


def test_subproblems_locate_returns_opinion_expression_fields() -> None:
    payload = locate_subproblems(_sample_reviews())
    first = payload[0].model_dump(mode="json")

    assert payload
    assert "opinion_expression" in first
    assert "evidence" not in first


def test_taxonomy_mine_returns_clusters_for_weak_annotations() -> None:
    payload = mine_taxonomy([_weak_prediction()])

    assert "Menu" in payload
    assert payload["Menu"]["clusters"]


def test_feedback_returns_accepted_payload() -> None:
    payload = recommendation_feedback(
        "rec_001",
        FeedbackPayload(
            implemented=True,
            implementation_date="2026-06-01",
            manager_rating=5,
            comment="Done",
        ),
    )

    assert payload.recommendation_id == "rec_001"
    assert payload.status == "accepted"
    assert payload.implemented is True


def _sample_reviews() -> list[ABSAReview]:
    return [
        ABSAReview.model_validate(json.loads(line))
        for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _weak_prediction() -> dict:
    return {
        "review_id": "weak_01",
        "aspect_category": "Menu",
        "aspect_expression": "combo",
        "opinion_expression": "không rõ gồm món gì",
        "sentiment": "negative",
        "model_confidence": 0.80,
        "predicted_sub_problem_id": "generic_menu_issue",
        "sub_problem_label": "Vấn đề chung về Menu",
        "locator_score": 0.30,
        "match_type": "generic",
        "needs_review": True,
        "severity": 0.75,
    }
