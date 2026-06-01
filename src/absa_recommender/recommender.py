from absa_recommender.models import AbsaOutput, ActionRecommendation


DEFAULT_ACTIONS = {
    "food": "Review dish preparation and ingredient consistency.",
    "service": "Coach staff on response time and table follow-up.",
    "price": "Check perceived value and menu price communication.",
    "ambience": "Inspect dining room comfort, cleanliness, and noise levels.",
}


def recommend_actions(record: AbsaOutput) -> list[ActionRecommendation]:
    recommendations: list[ActionRecommendation] = []
    for opinion in record.aspects:
        if opinion.sentiment != "negative":
            continue

        priority = "high" if opinion.score >= 0.8 else "medium"
        action = DEFAULT_ACTIONS.get(opinion.aspect, "Review this aspect and identify the root cause.")
        recommendations.append(
            ActionRecommendation(
                aspect=opinion.aspect,
                priority=priority,
                action=action,
                reason=opinion.text,
            )
        )
    return recommendations
