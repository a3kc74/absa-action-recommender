from absa_recommender.models import AbsaOutput, AspectOpinion
from absa_recommender.recommender import recommend_actions


def test_recommends_only_negative_aspects() -> None:
    record = AbsaOutput(
        review_id="rv_001",
        restaurant_id="rest_001",
        text="Good food, slow service.",
        aspects=[
            AspectOpinion(
                aspect="food",
                sentiment="positive",
                text="Good food",
                score=0.9,
            ),
            AspectOpinion(
                aspect="service",
                sentiment="negative",
                text="slow service",
                score=0.8,
            ),
        ],
    )

    recommendations = recommend_actions(record)

    assert len(recommendations) == 1
    assert recommendations[0].aspect == "service"
