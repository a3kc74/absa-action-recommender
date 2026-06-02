from pathlib import Path

from absa_recommender.api import (
    aspect_history,
    health,
    labels,
    monthly_run,
    peer_benchmark,
    priority_from_absa,
    restaurant_dashboard,
    restaurant_history,
    restaurant_priority,
)
from absa_recommender.normalize_absa import load_absa_jsonl


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_labels_include_official_aspects() -> None:
    payload = labels()

    assert "Food Quality" in payload["aspects"]
    assert "Menu" in payload["aspects"]


def test_priority_from_absa_returns_items() -> None:
    response = priority_from_absa(load_absa_jsonl(SAMPLE_PATH), top_n=5, restaurant_id="res_demo")

    assert response.items
    assert response.items[0].rank == 1


def test_monthly_and_dashboard_routes_have_priority_shape() -> None:
    monthly = monthly_run(load_absa_jsonl(SAMPLE_PATH), top_n=3, restaurant_id="res_demo")

    assert monthly.items
    assert restaurant_priority("res_demo", "2026-06")["status"] == "no_persisted_run"
    assert "overview" in restaurant_dashboard("res_demo", "2026-06")
    assert restaurant_history("res_demo")["runs"] == []
    assert aspect_history("res_demo", "Cleanliness")["history"] == []
    assert peer_benchmark("res_demo", "2026-06")["items"] == []
