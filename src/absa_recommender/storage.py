import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from absa_recommender.schemas import RecommendationResponse


def init_db(db_path: str | Path) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_runs (
                run_id VARCHAR PRIMARY KEY,
                restaurant_id VARCHAR,
                generated_at TIMESTAMP,
                input_hash VARCHAR,
                scoring_config_hash VARCHAR,
                model_version VARCHAR,
                output_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_items (
                recommendation_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                rank INTEGER,
                aspect VARCHAR,
                sub_problem_id VARCHAR,
                priority_score DOUBLE,
                confidence DOUBLE,
                component_scores_json VARCHAR,
                opinion_examples_json VARCHAR,
                actions_json VARCHAR,
                kpis_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subproblem_predictions (
                prediction_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                review_id VARCHAR,
                aspect_category VARCHAR,
                aspect_expression VARCHAR,
                opinion_expression VARCHAR,
                sentiment VARCHAR,
                model_confidence DOUBLE,
                predicted_sub_problem_id VARCHAR,
                locator_score DOUBLE,
                match_type VARCHAR,
                needs_review BOOLEAN
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS taxonomy_gap_reports (
                report_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                created_at TIMESTAMP,
                report_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id VARCHAR PRIMARY KEY,
                recommendation_id VARCHAR,
                implemented BOOLEAN,
                implementation_date DATE,
                manager_rating INTEGER,
                comment VARCHAR,
                created_at TIMESTAMP
            )
            """
        )


def save_recommendation_run(
    db_path: str | Path,
    response: RecommendationResponse,
    input_hash: str,
    scoring_config_hash: str,
    model_version: str = "unknown",
) -> str:
    init_db(db_path)
    run_id = _new_id("run")
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO recommendation_runs
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                response.restaurant_id,
                response.generated_at,
                input_hash,
                scoring_config_hash,
                model_version,
                response.model_dump_json(),
            ],
        )
    save_recommendation_items(db_path, run_id, response)
    return run_id


def save_recommendation_items(
    db_path: str | Path,
    run_id: str,
    response: RecommendationResponse,
) -> list[str]:
    init_db(db_path)
    recommendation_ids = []
    with _connect(db_path) as connection:
        for item in response.recommendations:
            recommendation_id = f"{run_id}_rank_{item.rank}"
            recommendation_ids.append(recommendation_id)
            connection.execute(
                """
                INSERT INTO recommendation_items
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    recommendation_id,
                    run_id,
                    item.rank,
                    item.aspect,
                    item.sub_problem_id,
                    item.priority_score,
                    item.confidence,
                    _json(item.component_scores),
                    _json(item.opinion_examples),
                    _json(item.recommended_actions),
                    _json(item.monitoring_kpis),
                ],
            )
    return recommendation_ids


def save_subproblem_predictions(
    db_path: str | Path,
    predictions: list[dict[str, Any]],
    run_id: str | None = None,
) -> list[str]:
    init_db(db_path)
    prediction_ids = []
    with _connect(db_path) as connection:
        for prediction in predictions:
            prediction_id = _new_id("pred")
            prediction_ids.append(prediction_id)
            connection.execute(
                """
                INSERT INTO subproblem_predictions
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    prediction_id,
                    run_id,
                    prediction.get("review_id"),
                    prediction.get("aspect_category"),
                    prediction.get("aspect_expression"),
                    prediction.get("opinion_expression"),
                    prediction.get("sentiment"),
                    prediction.get("model_confidence"),
                    prediction.get("predicted_sub_problem_id"),
                    prediction.get("locator_score"),
                    prediction.get("match_type"),
                    prediction.get("needs_review"),
                ],
            )
    return prediction_ids


def save_taxonomy_gap_report(
    db_path: str | Path,
    report: dict[str, Any],
    run_id: str | None = None,
) -> str:
    init_db(db_path)
    report_id = _new_id("report")
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO taxonomy_gap_reports
            VALUES (?, ?, ?, ?)
            """,
            [report_id, run_id, _now(), _json(report)],
        )
    return report_id


def save_feedback(
    db_path: str | Path,
    recommendation_id: str,
    implemented: bool,
    implementation_date: date | str | None,
    manager_rating: int | None,
    comment: str | None,
) -> str:
    init_db(db_path)
    feedback_id = _new_id("feedback")
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO feedback
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                feedback_id,
                recommendation_id,
                implemented,
                implementation_date,
                manager_rating,
                comment,
                _now(),
            ],
        )
    return feedback_id


def list_runs(db_path: str | Path, restaurant_id: str | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as connection:
        if restaurant_id is None:
            rows = connection.execute(
                """
                SELECT run_id, restaurant_id, generated_at, input_hash,
                       scoring_config_hash, model_version
                FROM recommendation_runs
                ORDER BY generated_at DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT run_id, restaurant_id, generated_at, input_hash,
                       scoring_config_hash, model_version
                FROM recommendation_runs
                WHERE restaurant_id = ?
                ORDER BY generated_at DESC
                """,
                [restaurant_id],
            ).fetchall()
    columns = [
        "run_id",
        "restaurant_id",
        "generated_at",
        "input_hash",
        "scoring_config_hash",
        "model_version",
    ]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def get_run(db_path: str | Path, run_id: str) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT run_id, restaurant_id, generated_at, input_hash,
                   scoring_config_hash, model_version, output_json
            FROM recommendation_runs
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()
    if row is None:
        return None
    columns = [
        "run_id",
        "restaurant_id",
        "generated_at",
        "input_hash",
        "scoring_config_hash",
        "model_version",
        "output_json",
    ]
    result = dict(zip(columns, row, strict=True))
    result["output"] = json.loads(result["output_json"])
    return result


def _connect(db_path: str | Path):
    return duckdb.connect(str(db_path))


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
