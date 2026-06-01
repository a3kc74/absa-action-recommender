from absa_recommender.evaluation import (
    generic_subproblem_rate,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    stability_score,
    weak_match_rate,
)


def test_precision_at_k() -> None:
    assert precision_at_k(["a", "b", "c"], ["a", "x"], 2) == 0.5


def test_recall_at_k() -> None:
    assert recall_at_k(["a", "b", "c"], ["a", "b", "x", "y"], 3) == 0.5


def test_ndcg_at_k() -> None:
    score = ndcg_at_k(["a", "b", "c"], {"a": 3, "b": 2, "c": 1}, 3)

    assert score == 1.0


def test_stability_overlap_at_k() -> None:
    assert stability_score(["a", "b", "c"], ["b", "c", "d"], 2) == 0.5


def test_generic_subproblem_rate() -> None:
    predictions = [
        {"predicted_sub_problem_id": "generic_menu_issue"},
        {"predicted_sub_problem_id": "dirty_tableware"},
    ]

    assert generic_subproblem_rate(predictions) == 0.5


def test_weak_match_rate() -> None:
    predictions = [
        {"locator_score": 0.30},
        {"locator_score": 0.80},
        {"locator_score": 0.44},
    ]

    assert weak_match_rate(predictions, threshold=0.45) == 2 / 3
