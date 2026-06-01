from pathlib import Path

from absa_recommender.normalize_absa import load_absa_jsonl
from absa_recommender.recommender import generate_recommendations
from absa_recommender.schemas import RecommendationItem


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


def test_end_to_end_sample_returns_recommendations() -> None:
    reviews = load_absa_jsonl(SAMPLE_PATH)

    response = generate_recommendations(reviews, top_n=5)

    assert response.restaurant_id == "multiple"
    assert response.recommendations
    assert response.recommendations[0].rank == 1


def test_location_and_menu_can_appear_in_recommendations() -> None:
    reviews = load_absa_jsonl(SAMPLE_PATH)

    response = generate_recommendations(reviews, top_n=5)
    aspects = {item.aspect for item in response.recommendations}

    assert "Location" in aspects
    assert "Menu" in aspects


def test_opinion_examples_come_from_opinion_expression() -> None:
    reviews = load_absa_jsonl(SAMPLE_PATH)

    response = generate_recommendations(reviews, top_n=5)
    examples = {
        example
        for item in response.recommendations
        for example in item.opinion_examples
    }

    assert "ghi món nhưng đến nơi lại hết món" in examples


def test_recommended_actions_are_non_empty() -> None:
    reviews = load_absa_jsonl(SAMPLE_PATH)

    response = generate_recommendations(reviews, top_n=5)

    assert all(item.recommended_actions for item in response.recommendations)
    assert all(item.monitoring_kpis for item in response.recommendations)


def test_output_is_json_serializable() -> None:
    reviews = load_absa_jsonl(SAMPLE_PATH)

    response = generate_recommendations(reviews, top_n=5)

    assert response.model_dump(mode="json")
    assert response.model_dump_json()


def test_no_internal_recommendation_field_named_evidence_is_required() -> None:
    assert "evidence" not in RecommendationItem.model_fields
