from absa_recommender.monitoring import (
    avg_locator_score,
    build_monitoring_snapshot,
    generic_rate_by_aspect,
    suggest_monitoring_alerts,
    top_unmatched_opinion_phrases,
    unreviewed_weak_or_generic_count,
    weak_match_rate_by_aspect,
)


def test_avg_locator_score() -> None:
    assert avg_locator_score(_predictions()) == (0.30 + 0.80 + 0.40 + 0.30 + 0.80) / 5


def test_generic_rate_by_aspect() -> None:
    rates = generic_rate_by_aspect(_predictions())

    assert rates["Menu"] == 1.0
    assert rates["Location"] == 0.0


def test_weak_match_rate_by_aspect() -> None:
    rates = weak_match_rate_by_aspect(_predictions(), threshold=0.45)

    assert rates["Menu"] == 1.0
    assert rates["Location"] == 0.5


def test_high_risk_unreviewed_counts() -> None:
    assert unreviewed_weak_or_generic_count(_predictions(), "Food Safety") == 1
    assert unreviewed_weak_or_generic_count(_predictions(), "Cleanliness") == 1


def test_top_unmatched_opinion_phrases() -> None:
    phrases = top_unmatched_opinion_phrases(_predictions(), limit=2)

    assert "không rõ gồm món gì" in phrases


def test_suggest_monitoring_alerts() -> None:
    alerts = suggest_monitoring_alerts(_predictions(), cleanliness_unreviewed_threshold=0)
    metrics = {alert["metric"] for alert in alerts}

    assert "generic_subproblem_rate" in metrics
    assert "generic_rate_by_aspect.Menu" in metrics
    assert "food_safety_unreviewed_count" in metrics
    assert "cleanliness_unreviewed_count" in metrics


def test_build_monitoring_snapshot() -> None:
    snapshot = build_monitoring_snapshot(
        recommendation_responses=[
            {
                "recommendations": [
                    {
                        "aspect": "Menu",
                        "sub_problem_id": "generic_menu_issue",
                        "confidence": 0.8,
                        "recommended_actions": ["Review menu."],
                    }
                ]
            }
        ],
        predictions=_predictions(),
    )

    assert "recommendation_coverage" in snapshot
    assert "top_unmatched_opinion_phrases" in snapshot
    assert snapshot["action_coverage"] == 1.0


def _predictions() -> list[dict]:
    return [
        {
            "aspect_category": "Menu",
            "opinion_expression": "không rõ gồm món gì",
            "predicted_sub_problem_id": "generic_menu_issue",
            "locator_score": 0.30,
            "needs_review": True,
        },
        {
            "aspect_category": "Location",
            "opinion_expression": "khó tìm",
            "predicted_sub_problem_id": "hard_to_find",
            "locator_score": 0.80,
            "needs_review": False,
        },
        {
            "aspect_category": "Location",
            "opinion_expression": "đường vào mơ hồ",
            "predicted_sub_problem_id": "hard_to_find",
            "locator_score": 0.40,
            "needs_review": False,
        },
        {
            "aspect_category": "Food Safety",
            "opinion_expression": "đau bụng",
            "predicted_sub_problem_id": "generic_food_safety_issue",
            "locator_score": 0.30,
            "needs_review": False,
        },
        {
            "aspect_category": "Cleanliness",
            "opinion_expression": "ly có vệt đen",
            "predicted_sub_problem_id": "dirty_tableware",
            "locator_score": 0.80,
            "needs_review": True,
        },
    ]
