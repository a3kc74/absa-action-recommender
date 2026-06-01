import math
from typing import Any

from absa_recommender.schemas import RecommendationResponse


def recommendation_coverage(
    recommendation_responses: list[RecommendationResponse] | list[dict[str, Any]],
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    items = [
        item
        for response in recommendation_responses
        for item in _recommendation_items(response)
        if float(_get(item, "confidence", 0.0)) >= min_confidence
    ]
    aspects = {_get(item, "aspect") for item in items}
    sub_problem_ids = {_get(item, "sub_problem_id") for item in items}
    return {
        "recommendation_count": len(items),
        "aspect_count": len(aspects),
        "sub_problem_count": len(sub_problem_ids),
        "aspects": sorted(aspect for aspect in aspects if aspect is not None),
    }


def subproblem_coverage(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    sub_problem_ids = {
        prediction.get("predicted_sub_problem_id")
        for prediction in predictions
        if prediction.get("predicted_sub_problem_id")
    }
    return {
        "prediction_count": len(predictions),
        "sub_problem_count": len(sub_problem_ids),
        "sub_problem_ids": sorted(sub_problem_ids),
    }


def generic_subproblem_rate(predictions: list[dict[str, Any]]) -> float:
    if not predictions:
        return 0.0
    generic_count = sum(
        str(prediction.get("predicted_sub_problem_id", "")).startswith("generic_")
        for prediction in predictions
    )
    return generic_count / len(predictions)


def weak_match_rate(predictions: list[dict[str, Any]], threshold: float = 0.45) -> float:
    if not predictions:
        return 0.0
    weak_count = sum(float(prediction.get("locator_score", 0.0)) < threshold for prediction in predictions)
    return weak_count / len(predictions)


def action_coverage(recommendations: list[dict[str, Any]]) -> float:
    if not recommendations:
        return 0.0
    covered = sum(bool(recommendation.get("recommended_actions")) for recommendation in recommendations)
    return covered / len(recommendations)


def precision_at_k(
    predicted_sub_problem_ids: list[str],
    gold_sub_problem_ids: list[str],
    k: int,
) -> float:
    if k <= 0:
        return 0.0
    predicted_at_k = predicted_sub_problem_ids[:k]
    if not predicted_at_k:
        return 0.0
    gold = set(gold_sub_problem_ids)
    hits = sum(prediction in gold for prediction in predicted_at_k)
    return hits / len(predicted_at_k)


def recall_at_k(
    predicted_sub_problem_ids: list[str],
    gold_sub_problem_ids: list[str],
    k: int,
) -> float:
    if k <= 0 or not gold_sub_problem_ids:
        return 0.0
    predicted_at_k = set(predicted_sub_problem_ids[:k])
    gold = set(gold_sub_problem_ids)
    return len(predicted_at_k & gold) / len(gold)


def ndcg_at_k(predicted_ids: list[str], relevance_by_id: dict[str, float], k: int) -> float:
    if k <= 0:
        return 0.0
    dcg = _dcg([relevance_by_id.get(item_id, 0.0) for item_id in predicted_ids[:k]])
    ideal_relevances = sorted(relevance_by_id.values(), reverse=True)[:k]
    ideal_dcg = _dcg(ideal_relevances)
    if ideal_dcg == 0:
        return 0.0
    return dcg / ideal_dcg


def stability_score(
    original_ranking: list[str],
    perturbed_ranking: list[str],
    k: int,
) -> float:
    if k <= 0:
        return 0.0
    original_top = set(original_ranking[:k])
    perturbed_top = set(perturbed_ranking[:k])
    return len(original_top & perturbed_top) / k


def evaluate_recommendation_file(
    predictions_payload: dict[str, Any],
    gold_payload: dict[str, Any],
    k: int,
) -> dict[str, float]:
    predicted_ids = [
        item["sub_problem_id"]
        for item in predictions_payload.get("recommendations", [])
    ]
    gold_ids = gold_payload.get("relevant_sub_problem_ids", [])
    relevance = {sub_problem_id: 1.0 for sub_problem_id in gold_ids}
    return {
        "precision_at_k": precision_at_k(predicted_ids, gold_ids, k),
        "recall_at_k": recall_at_k(predicted_ids, gold_ids, k),
        "ndcg_at_k": ndcg_at_k(predicted_ids, relevance, k),
    }


def _dcg(relevances: list[float]) -> float:
    return sum(
        (2**relevance - 1) / math.log2(index + 2)
        for index, relevance in enumerate(relevances)
    )


def _recommendation_items(response: RecommendationResponse | dict[str, Any]) -> list[Any]:
    if isinstance(response, RecommendationResponse):
        return list(response.recommendations)
    return list(response.get("recommendations", []))


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)
