from pathlib import Path

from absa_recommender.actions import get_actions, load_action_catalog


CATALOG = load_action_catalog(Path("configs/action_catalog.yaml"))


def test_cleanliness_dirty_tableware_returns_actions_and_kpis() -> None:
    recommendation = get_actions("Cleanliness", "dirty_tableware", CATALOG)

    assert recommendation.aspect == "Cleanliness"
    assert recommendation.sub_problem_id == "dirty_tableware"
    assert recommendation.actions
    assert recommendation.kpis


def test_location_parking_issue_returns_actions_and_kpis() -> None:
    recommendation = get_actions("Location", "parking_issue", CATALOG)

    assert recommendation.aspect == "Location"
    assert recommendation.sub_problem_id == "parking_issue"
    assert recommendation.actions
    assert recommendation.kpis


def test_menu_item_unavailable_returns_actions_and_kpis() -> None:
    recommendation = get_actions("Menu", "menu_item_unavailable", CATALOG)

    assert recommendation.aspect == "Menu"
    assert recommendation.sub_problem_id == "menu_item_unavailable"
    assert recommendation.actions
    assert recommendation.kpis


def test_unknown_sub_problem_returns_generic_aspect_action() -> None:
    recommendation = get_actions("Menu", "unknown_menu_problem", CATALOG)

    assert recommendation.aspect == "Menu"
    assert recommendation.sub_problem_id == "generic_menu_issue"
    assert recommendation.actions
    assert recommendation.kpis


def test_unknown_aspect_returns_unknown_generic_action() -> None:
    recommendation = get_actions("Delivery", "late_delivery", CATALOG)

    assert recommendation.aspect == "Unknown"
    assert recommendation.sub_problem_id == "generic_unknown_issue"
    assert recommendation.actions
    assert recommendation.kpis
