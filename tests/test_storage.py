from pathlib import Path

import duckdb

from absa_recommender.normalize_absa import load_absa_jsonl
from absa_recommender.recommender import generate_recommendations
from absa_recommender.storage import (
    get_run,
    init_db,
    list_runs,
    save_feedback,
    save_recommendation_run,
    save_subproblem_predictions,
    save_taxonomy_gap_report,
)


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"

    init_db(db_path)

    with duckdb.connect(str(db_path)) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
    assert "recommendation_runs" in tables
    assert "recommendation_items" in tables
    assert "feedback" in tables


def test_save_recommendation_run_and_items(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"
    response = generate_recommendations(load_absa_jsonl(SAMPLE_PATH), top_n=3)

    run_id = save_recommendation_run(
        db_path,
        response,
        input_hash="input_hash",
        scoring_config_hash="scoring_hash",
        model_version="test",
    )

    run = get_run(db_path, run_id)
    runs = list_runs(db_path)
    with duckdb.connect(str(db_path)) as connection:
        item_count = connection.execute(
            "SELECT COUNT(*) FROM recommendation_items WHERE run_id = ?",
            [run_id],
        ).fetchone()[0]

    assert run is not None
    assert run["run_id"] == run_id
    assert run["output"]["recommendations"]
    assert runs[0]["run_id"] == run_id
    assert item_count == len(response.recommendations)


def test_list_runs_filters_by_restaurant_id(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"
    response = generate_recommendations(load_absa_jsonl(SAMPLE_PATH), top_n=2)

    save_recommendation_run(db_path, response, "input", "scoring")

    assert list_runs(db_path, restaurant_id=response.restaurant_id)
    assert list_runs(db_path, restaurant_id="missing") == []


def test_save_subproblem_predictions(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"
    prediction_ids = save_subproblem_predictions(
        db_path,
        [
            {
                "review_id": "rv_001",
                "aspect_category": "Menu",
                "aspect_expression": "menu",
                "opinion_expression": "hết món",
                "sentiment": "negative",
                "model_confidence": 0.9,
                "predicted_sub_problem_id": "menu_item_unavailable",
                "locator_score": 0.8,
                "match_type": "rule",
                "needs_review": False,
            }
        ],
        run_id="run_001",
    )

    with duckdb.connect(str(db_path)) as connection:
        row = connection.execute("SELECT opinion_expression FROM subproblem_predictions").fetchone()

    assert prediction_ids
    assert row[0] == "hết món"


def test_save_taxonomy_gap_report(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"
    report_id = save_taxonomy_gap_report(
        db_path,
        {"Menu": {"clusters": [{"cluster_id": "Menu_01"}]}},
        run_id="run_001",
    )

    with duckdb.connect(str(db_path)) as connection:
        row = connection.execute("SELECT report_json FROM taxonomy_gap_reports").fetchone()

    assert report_id.startswith("report_")
    assert "Menu_01" in row[0]


def test_save_feedback(tmp_path: Path) -> None:
    db_path = tmp_path / "local.duckdb"
    feedback_id = save_feedback(
        db_path,
        recommendation_id="rec_001",
        implemented=True,
        implementation_date="2026-06-02",
        manager_rating=5,
        comment="Done",
    )

    with duckdb.connect(str(db_path)) as connection:
        row = connection.execute("SELECT implemented, manager_rating FROM feedback").fetchone()

    assert feedback_id.startswith("feedback_")
    assert row == (True, 5)
