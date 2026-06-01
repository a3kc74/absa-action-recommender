from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from absa_recommender.actions import get_actions, load_action_catalog
from absa_recommender.aggregation import aggregate_aspect_stats
from absa_recommender.config import load_label_schema, load_yaml
from absa_recommender.normalize_absa import flatten_reviews
from absa_recommender.prototype_matcher import load_subproblem_prototypes
from absa_recommender.schemas import (
    ABSAReview,
    AspectExtraction,
    AspectRecommendationCandidate,
    AspectStats,
    RecommendationItem,
    RecommendationResponse,
    SubProblemPrediction,
)
from absa_recommender.scoring import (
    benchmark_gap,
    combined_confidence,
    compute_global_negative_rate_by_aspect,
    compute_priority_score,
    log_mention_share,
    model_confidence,
    normalized_rating_gap,
    smoothed_negative_rate,
    support_confidence,
)
from absa_recommender.severity import load_severity_config
from absa_recommender.subproblem import compute_subproblem_score, load_subproblem_rules
from absa_recommender.subproblem_locator import locate_subproblem


DEFAULT_CONFIG_PATHS = {
    "label_schema": Path("configs/label_schema.yaml"),
    "scoring": Path("configs/scoring.yaml"),
    "severity": Path("configs/severity_lexicon.yaml"),
    "subproblem_rules": Path("configs/subproblem_rules.yaml"),
    "subproblem_prototypes": Path("configs/subproblem_prototypes.yaml"),
    "locator": Path("configs/locator.yaml"),
    "action_catalog": Path("configs/action_catalog.yaml"),
}


def generate_recommendations(
    reviews_or_extractions: list[ABSAReview] | list[AspectExtraction],
    top_n: int = 5,
    config_paths: dict[str, str | Path] | None = None,
    default_restaurant_id: str = "unknown",
) -> RecommendationResponse:
    configs = _load_configs(config_paths)
    extractions = _ensure_extractions(
        reviews_or_extractions,
        configs["label_schema"],
        configs["severity"],
        default_restaurant_id,
    )
    restaurant_id = _response_restaurant_id(extractions, default_restaurant_id)
    if not extractions:
        return RecommendationResponse(
            restaurant_id=restaurant_id,
            generated_at=_now(),
            recommendations=[],
        )

    stats = aggregate_aspect_stats(extractions, configs["scoring"])
    global_negative_rates = compute_global_negative_rate_by_aspect(
        extractions,
        configs["label_schema"],
    )
    candidates = [
        _build_candidate(stat, global_negative_rates, configs["scoring"])
        for stat in stats
        if stat.negative_count > 0
    ]
    negative_extractions = [item for item in extractions if item.sentiment == "negative"]
    recommendations = [
        _recommend_for_candidate(candidate, negative_extractions, configs)
        for candidate in candidates
    ]
    recommendations = [item for item in recommendations if item is not None]
    recommendations = _apply_food_safety_top3(recommendations, configs["scoring"], top_n)
    recommendations = recommendations[:top_n]

    ranked = [
        item.model_copy(update={"rank": rank})
        for rank, item in enumerate(recommendations, start=1)
    ]
    return RecommendationResponse(
        restaurant_id=restaurant_id,
        generated_at=_now(),
        recommendations=ranked,
    )


def _load_configs(config_paths: dict[str, str | Path] | None) -> dict[str, Any]:
    paths = {**DEFAULT_CONFIG_PATHS, **(config_paths or {})}
    return {
        "label_schema": load_label_schema(paths["label_schema"]),
        "scoring": load_yaml(paths["scoring"]),
        "severity": load_severity_config(paths["severity"]),
        "subproblem_rules": load_subproblem_rules(paths["subproblem_rules"]),
        "subproblem_prototypes": load_subproblem_prototypes(paths["subproblem_prototypes"]),
        "locator": load_yaml(paths["locator"]),
        "action_catalog": load_action_catalog(paths["action_catalog"]),
    }


def _ensure_extractions(
    reviews_or_extractions: list[ABSAReview] | list[AspectExtraction],
    label_schema: dict[str, Any],
    severity_config: dict[str, Any],
    default_restaurant_id: str,
) -> list[AspectExtraction]:
    if not reviews_or_extractions:
        return []
    first = reviews_or_extractions[0]
    if isinstance(first, AspectExtraction):
        return list(reviews_or_extractions)
    return flatten_reviews(
        list(reviews_or_extractions),
        label_schema,
        default_restaurant_id=default_restaurant_id,
        severity_config=severity_config,
    )


def _build_candidate(
    stats: AspectStats,
    global_negative_rates: dict[str, float],
    scoring_config: dict[str, Any],
) -> AspectRecommendationCandidate:
    scoring = scoring_config.get("scoring", scoring_config)
    alpha = float(scoring.get("smoothing", {}).get("alpha", 10))
    tau = float(scoring.get("confidence", {}).get("support_threshold_tau", 30))
    lambda_support = float(scoring.get("confidence", {}).get("lambda_support", 0.7))
    neg_rate = smoothed_negative_rate(
        stats.negative_count,
        stats.mention_count,
        global_negative_rates.get(stats.aspect, 0.0),
        alpha,
    )
    support_conf = support_confidence(stats.mention_count, tau)
    model_conf = model_confidence(stats.avg_confidence)
    confidence = combined_confidence(support_conf, model_conf, lambda_support)
    component_scores = {
        "negative_rate": neg_rate,
        "sentiment_severity": stats.avg_severity,
        "mention_share": log_mention_share(
            stats.mention_count,
            stats.total_mentions_for_restaurant,
        ),
        "rating_gap": normalized_rating_gap(stats.avg_rating),
        "trend_score": _trend_score(stats, scoring),
        "benchmark_gap": benchmark_gap(neg_rate, None),
    }
    return AspectRecommendationCandidate(
        restaurant_id=stats.restaurant_id,
        aspect=stats.aspect,
        priority_score=compute_priority_score(stats, component_scores, scoring_config),
        confidence=confidence,
        severity=stats.avg_severity,
        mention_count=stats.mention_count,
        negative_count=stats.negative_count,
        component_scores=component_scores,
    )


def _recommend_for_candidate(
    candidate: AspectRecommendationCandidate,
    negative_extractions: list[AspectExtraction],
    configs: dict[str, Any],
) -> RecommendationItem | None:
    aspect_extractions = [
        item
        for item in negative_extractions
        if item.restaurant_id == candidate.restaurant_id and item.aspect == candidate.aspect
    ]
    if not aspect_extractions:
        return None

    predictions = [
        locate_subproblem(
            extraction,
            configs["subproblem_rules"],
            configs["subproblem_prototypes"],
            configs["locator"],
        )
        for extraction in aspect_extractions
    ]
    prediction_groups: dict[str, list[tuple[AspectExtraction, SubProblemPrediction]]] = defaultdict(list)
    for extraction, prediction in zip(aspect_extractions, predictions, strict=True):
        prediction_groups[prediction.predicted_sub_problem_id].append((extraction, prediction))

    subproblem_id, group = _top_subproblem_group(prediction_groups, candidate.priority_score)
    group_extractions = [item[0] for item in group]
    group_predictions = [item[1] for item in group]
    group_share = len(group) / len(aspect_extractions)
    severity = _mean([item.severity for item in group_extractions])
    priority_score = compute_subproblem_score(
        candidate.priority_score,
        group_share,
        severity,
    )
    representative_prediction = group_predictions[0]
    action_recommendation = get_actions(
        candidate.aspect,
        subproblem_id,
        configs["action_catalog"],
    )

    return RecommendationItem(
        rank=0,
        aspect=candidate.aspect,
        sub_problem_id=subproblem_id,
        sub_problem_label=representative_prediction.sub_problem_label,
        priority_score=priority_score,
        confidence=candidate.confidence,
        severity=severity,
        mention_count=len(group_extractions),
        negative_count=len(group_extractions),
        opinion_examples=_opinion_examples(group_extractions),
        recommended_actions=action_recommendation.actions,
        monitoring_kpis=action_recommendation.kpis,
        component_scores=candidate.component_scores,
        locator_summary=dict(Counter(item.match_type for item in group_predictions)),
    )


def _top_subproblem_group(
    groups: dict[str, list[tuple[AspectExtraction, SubProblemPrediction]]],
    parent_priority_score: float,
) -> tuple[str, list[tuple[AspectExtraction, SubProblemPrediction]]]:
    return max(
        groups.items(),
        key=lambda item: (
            compute_subproblem_score(
                parent_priority_score,
                len(item[1]) / sum(len(group) for group in groups.values()),
                _mean([pair[0].severity for pair in item[1]]),
            ),
            len(item[1]),
        ),
    )


def _apply_food_safety_top3(
    recommendations: list[RecommendationItem],
    scoring_config: dict[str, Any],
    top_n: int,
) -> list[RecommendationItem]:
    sorted_items = sorted(recommendations, key=lambda item: item.priority_score, reverse=True)
    scoring = scoring_config.get("scoring", scoring_config)
    safety_rules = scoring.get("safety_rules", {})
    if not safety_rules.get("force_food_safety_top3", False) or top_n < 3:
        return sorted_items

    food_safety_index = next(
        (index for index, item in enumerate(sorted_items) if item.aspect == "Food Safety"),
        None,
    )
    if food_safety_index is None or food_safety_index < 3:
        return sorted_items

    food_safety_item = sorted_items.pop(food_safety_index)
    sorted_items.insert(2, food_safety_item)
    return sorted_items


def _trend_score(stats: AspectStats, scoring: dict[str, Any]) -> float:
    if stats.window_start is None or stats.window_end is None:
        return float(scoring.get("defaults", {}).get("trend_if_missing", 0.0))
    return 0.0


def _opinion_examples(extractions: list[AspectExtraction], limit: int = 3) -> list[str]:
    examples: list[str] = []
    for extraction in extractions:
        if extraction.opinion_text not in examples:
            examples.append(extraction.opinion_text)
        if len(examples) >= limit:
            break
    return examples


def _response_restaurant_id(
    extractions: list[AspectExtraction],
    default_restaurant_id: str,
) -> str:
    restaurant_ids = sorted({item.restaurant_id for item in extractions})
    if not restaurant_ids:
        return default_restaurant_id
    if len(restaurant_ids) == 1:
        return restaurant_ids[0]
    return "multiple"


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _now() -> datetime:
    return datetime.now(timezone.utc)
