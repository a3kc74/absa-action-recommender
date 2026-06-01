from collections import defaultdict
from typing import Any

from absa_recommender.evaluation import (
    action_coverage,
    generic_subproblem_rate,
    recommendation_coverage,
    subproblem_coverage,
    weak_match_rate,
)
from absa_recommender.phrase_miner import top_opinion_phrases


def build_monitoring_snapshot(
    recommendation_responses: list[Any] | None = None,
    predictions: list[dict[str, Any]] | None = None,
    weak_threshold: float = 0.45,
    cleanliness_unreviewed_threshold: int = 0,
    top_phrase_limit: int = 10,
) -> dict[str, Any]:
    responses = recommendation_responses or []
    prediction_rows = predictions or []
    recommendations = [
        item
        for response in responses
        for item in _recommendation_items(response)
    ]
    return {
        "recommendation_coverage": recommendation_coverage(responses),
        "subproblem_coverage": subproblem_coverage(prediction_rows),
        "generic_subproblem_rate": generic_subproblem_rate(prediction_rows),
        "weak_match_rate": weak_match_rate(prediction_rows, threshold=weak_threshold),
        "action_coverage": action_coverage(recommendations),
        "avg_locator_score": avg_locator_score(prediction_rows),
        "generic_rate_by_aspect": generic_rate_by_aspect(prediction_rows),
        "weak_match_rate_by_aspect": weak_match_rate_by_aspect(
            prediction_rows,
            threshold=weak_threshold,
        ),
        "food_safety_unreviewed_count": unreviewed_weak_or_generic_count(
            prediction_rows,
            "Food Safety",
            threshold=weak_threshold,
        ),
        "cleanliness_unreviewed_count": unreviewed_weak_or_generic_count(
            prediction_rows,
            "Cleanliness",
            threshold=weak_threshold,
        ),
        "top_unmatched_opinion_phrases": top_unmatched_opinion_phrases(
            prediction_rows,
            limit=top_phrase_limit,
            threshold=weak_threshold,
        ),
        "alerts": suggest_monitoring_alerts(
            prediction_rows,
            weak_threshold=weak_threshold,
            cleanliness_unreviewed_threshold=cleanliness_unreviewed_threshold,
        ),
    }


def avg_locator_score(predictions: list[dict[str, Any]]) -> float:
    if not predictions:
        return 0.0
    return sum(float(prediction.get("locator_score", 0.0)) for prediction in predictions) / len(
        predictions
    )


def generic_rate_by_aspect(predictions: list[dict[str, Any]]) -> dict[str, float]:
    grouped = _group_by_aspect(predictions)
    return {
        aspect: generic_subproblem_rate(rows)
        for aspect, rows in grouped.items()
    }


def weak_match_rate_by_aspect(
    predictions: list[dict[str, Any]],
    threshold: float = 0.45,
) -> dict[str, float]:
    grouped = _group_by_aspect(predictions)
    return {
        aspect: weak_match_rate(rows, threshold=threshold)
        for aspect, rows in grouped.items()
    }


def unreviewed_weak_or_generic_count(
    predictions: list[dict[str, Any]],
    aspect: str,
    threshold: float = 0.45,
) -> int:
    return sum(
        prediction.get("aspect_category") == aspect
        and not bool(prediction.get("reviewed", False))
        and (
            str(prediction.get("predicted_sub_problem_id", "")).startswith("generic_")
            or float(prediction.get("locator_score", 0.0)) < threshold
            or bool(prediction.get("needs_review", False))
        )
        for prediction in predictions
    )


def top_unmatched_opinion_phrases(
    predictions: list[dict[str, Any]],
    limit: int = 10,
    threshold: float = 0.45,
) -> list[str]:
    unmatched = [
        prediction
        for prediction in predictions
        if str(prediction.get("predicted_sub_problem_id", "")).startswith("generic_")
        or float(prediction.get("locator_score", 0.0)) < threshold
        or bool(prediction.get("needs_review", False))
    ]
    return top_opinion_phrases(unmatched, limit)


def suggest_monitoring_alerts(
    predictions: list[dict[str, Any]],
    weak_threshold: float = 0.45,
    generic_rate_threshold: float = 0.25,
    menu_generic_rate_threshold: float = 0.35,
    cleanliness_unreviewed_threshold: int = 0,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    generic_rate = generic_subproblem_rate(predictions)
    generic_by_aspect = generic_rate_by_aspect(predictions)
    food_safety_count = unreviewed_weak_or_generic_count(
        predictions,
        "Food Safety",
        threshold=weak_threshold,
    )
    cleanliness_count = unreviewed_weak_or_generic_count(
        predictions,
        "Cleanliness",
        threshold=weak_threshold,
    )

    if generic_rate > generic_rate_threshold:
        alerts.append(
            {
                "metric": "generic_subproblem_rate",
                "value": generic_rate,
                "message": "Generic sub-problem rate is high; run taxonomy miner.",
            }
        )
    if generic_by_aspect.get("Menu", 0.0) > menu_generic_rate_threshold:
        alerts.append(
            {
                "metric": "generic_rate_by_aspect.Menu",
                "value": generic_by_aspect["Menu"],
                "message": "Menu taxonomy is likely missing rules.",
            }
        )
    if food_safety_count > 0:
        alerts.append(
            {
                "metric": "food_safety_unreviewed_count",
                "value": food_safety_count,
                "message": "Food Safety weak/generic annotations require immediate review.",
            }
        )
    if cleanliness_count > cleanliness_unreviewed_threshold:
        alerts.append(
            {
                "metric": "cleanliness_unreviewed_count",
                "value": cleanliness_count,
                "message": "Cleanliness weak/generic annotations require manual review.",
            }
        )
    return alerts


def _group_by_aspect(predictions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prediction in predictions:
        grouped[prediction.get("aspect_category", "Unknown")].append(prediction)
    return dict(grouped)


def _recommendation_items(response: Any) -> list[dict[str, Any]]:
    if isinstance(response, dict):
        return list(response.get("recommendations", []))
    return [
        item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        for item in getattr(response, "recommendations", [])
    ]
