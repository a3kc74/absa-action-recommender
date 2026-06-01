from collections import defaultdict
from typing import Any

from absa_recommender.schemas import AspectExtraction, AspectStats


def aggregate_aspect_stats(
    extractions: list[AspectExtraction],
    scoring_config: dict[str, Any],
) -> list[AspectStats]:
    scoring = scoring_config.get("scoring", scoring_config)
    default_rating = float(scoring.get("defaults", {}).get("rating_if_missing", 3.5))
    default_confidence = float(
        scoring.get("confidence", {}).get("default_missing_confidence", 0.75)
    )

    total_mentions_by_restaurant: dict[str, int] = defaultdict(int)
    grouped: dict[tuple[str, str], list[AspectExtraction]] = defaultdict(list)
    for extraction in extractions:
        total_mentions_by_restaurant[extraction.restaurant_id] += 1
        grouped[(extraction.restaurant_id, extraction.aspect)].append(extraction)

    stats = [
        _build_aspect_stats(
            restaurant_id=restaurant_id,
            aspect=aspect,
            group=group,
            total_mentions_for_restaurant=total_mentions_by_restaurant[restaurant_id],
            default_rating=default_rating,
            default_confidence=default_confidence,
        )
        for (restaurant_id, aspect), group in grouped.items()
    ]
    return sorted(stats, key=lambda item: (item.restaurant_id, item.aspect))


def _build_aspect_stats(
    restaurant_id: str,
    aspect: str,
    group: list[AspectExtraction],
    total_mentions_for_restaurant: int,
    default_rating: float,
    default_confidence: float,
) -> AspectStats:
    review_times = [item.review_time for item in group if item.review_time is not None]
    return AspectStats(
        restaurant_id=restaurant_id,
        aspect=aspect,
        mention_count=len(group),
        negative_count=sum(item.sentiment == "negative" for item in group),
        positive_count=sum(item.sentiment == "positive" for item in group),
        neutral_count=sum(item.sentiment == "neutral" for item in group),
        avg_severity=_mean([item.severity for item in group]),
        avg_rating=_mean(
            [float(item.rating) if item.rating is not None else default_rating for item in group]
        ),
        avg_confidence=_mean(
            [
                item.model_confidence
                if item.model_confidence is not None
                else default_confidence
                for item in group
            ]
        ),
        total_mentions_for_restaurant=total_mentions_for_restaurant,
        window_start=min(review_times) if review_times else None,
        window_end=max(review_times) if review_times else None,
    )


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
