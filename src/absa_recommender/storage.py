import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from absa_recommender.schemas import PriorityResponse


def init_db(db_path: str | Path) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS restaurants (
                restaurant_id VARCHAR PRIMARY KEY,
                source VARCHAR,
                source_place_id VARCHAR,
                name VARCHAR,
                lat DOUBLE,
                lng DOUBLE,
                area_id VARCHAR,
                is_target BOOLEAN,
                is_peer BOOLEAN,
                status VARCHAR,
                first_seen_at TIMESTAMP,
                last_seen_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_runs (
                crawl_run_id VARCHAR PRIMARY KEY,
                source VARCHAR,
                target_month VARCHAR,
                area_id VARCHAR,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                status VARCHAR,
                num_restaurants INTEGER,
                num_reviews_fetched INTEGER,
                num_reviews_inserted INTEGER,
                num_duplicates INTEGER,
                error_message VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                review_id VARCHAR PRIMARY KEY,
                crawl_run_id VARCHAR,
                restaurant_id VARCHAR,
                source VARCHAR,
                source_review_id VARCHAR,
                review_text VARCHAR,
                review_text_hash VARCHAR,
                rating INTEGER,
                review_time TIMESTAMP,
                review_month VARCHAR,
                language VARCHAR,
                fetched_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS absa_annotations (
                annotation_id VARCHAR PRIMARY KEY,
                review_id VARCHAR,
                restaurant_id VARCHAR,
                review_month VARCHAR,
                aspect VARCHAR,
                aspect_term VARCHAR,
                opinion_text VARCHAR,
                sentiment VARCHAR,
                model_confidence DOUBLE,
                severity DOUBLE,
                absa_model_version VARCHAR,
                created_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS aspect_monthly_stats (
                restaurant_id VARCHAR,
                review_month VARCHAR,
                aspect VARCHAR,
                mention_count INTEGER,
                negative_count INTEGER,
                positive_count INTEGER,
                neutral_count INTEGER,
                negative_rate_raw DOUBLE,
                negative_rate_smoothed DOUBLE,
                avg_severity DOUBLE,
                avg_rating DOUBLE,
                avg_confidence DOUBLE,
                mention_share DOUBLE,
                rating_gap DOUBLE,
                total_mentions_for_restaurant INTEGER,
                PRIMARY KEY (restaurant_id, review_month, aspect)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_aspect_monthly_stats (
                area_id VARCHAR,
                target_restaurant_id VARCHAR,
                review_month VARCHAR,
                aspect VARCHAR,
                peer_restaurant_count INTEGER,
                peer_total_mentions INTEGER,
                peer_negative_rate DOUBLE,
                peer_avg_severity DOUBLE,
                peer_avg_rating DOUBLE,
                peer_p50_negative_rate DOUBLE,
                peer_p75_negative_rate DOUBLE,
                peer_p90_negative_rate DOUBLE,
                peer_support_confidence DOUBLE,
                PRIMARY KEY (area_id, target_restaurant_id, review_month, aspect)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS priority_runs (
                priority_run_id VARCHAR PRIMARY KEY,
                restaurant_id VARCHAR,
                review_month VARCHAR,
                generated_at TIMESTAMP,
                crawl_run_id VARCHAR,
                absa_model_version VARCHAR,
                scoring_config_hash VARCHAR,
                status VARCHAR,
                output_json VARCHAR
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS priority_items (
                priority_run_id VARCHAR,
                restaurant_id VARCHAR,
                review_month VARCHAR,
                rank INTEGER,
                aspect VARCHAR,
                priority_score DOUBLE,
                priority_confidence DOUBLE,
                severity DOUBLE,
                mention_count INTEGER,
                negative_count INTEGER,
                negative_rate_smoothed DOUBLE,
                mention_share DOUBLE,
                rating_gap DOUBLE,
                trend_score DOUBLE,
                benchmark_gap DOUBLE,
                risk_multiplier DOUBLE,
                component_scores_json VARCHAR,
                peer_summary_json VARCHAR,
                trend_summary_json VARCHAR,
                opinion_examples_json VARCHAR,
                data_quality_flags_json VARCHAR,
                PRIMARY KEY (priority_run_id, rank)
            )
            """
        )


def save_priority_run(
    db_path: str | Path,
    response: PriorityResponse,
    scoring_config_hash: str,
    crawl_run_id: str | None = None,
    absa_model_version: str = "unknown",
    status: str = "completed",
) -> str:
    init_db(db_path)
    run_id = _new_id("priority")
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO priority_runs
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                response.restaurant_id,
                response.review_month,
                response.generated_at,
                crawl_run_id,
                absa_model_version,
                scoring_config_hash,
                status,
                response.model_dump_json(),
            ],
        )
    save_priority_items(db_path, run_id, response)
    return run_id


def save_priority_items(
    db_path: str | Path,
    priority_run_id: str,
    response: PriorityResponse,
) -> None:
    init_db(db_path)
    with _connect(db_path) as connection:
        for item in response.items:
            connection.execute(
                """
                INSERT INTO priority_items
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    priority_run_id,
                    response.restaurant_id,
                    response.review_month,
                    item.rank,
                    item.aspect,
                    item.priority_score,
                    item.priority_confidence,
                    item.severity,
                    item.mention_count,
                    item.negative_count,
                    item.negative_rate_smoothed,
                    item.mention_share,
                    item.rating_gap,
                    item.trend_score,
                    item.benchmark_gap,
                    item.risk_multiplier,
                    _json(item.component_scores),
                    item.peer_summary.model_dump_json(),
                    item.trend_summary.model_dump_json(),
                    _json(item.opinion_examples),
                    _json(item.data_quality_flags),
                ],
            )


def list_priority_runs(db_path: str | Path, restaurant_id: str | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as connection:
        if restaurant_id is None:
            rows = connection.execute(
                """
                SELECT priority_run_id, restaurant_id, review_month, generated_at,
                       crawl_run_id, absa_model_version, scoring_config_hash, status
                FROM priority_runs
                ORDER BY generated_at DESC
                """
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT priority_run_id, restaurant_id, review_month, generated_at,
                       crawl_run_id, absa_model_version, scoring_config_hash, status
                FROM priority_runs
                WHERE restaurant_id = ?
                ORDER BY generated_at DESC
                """,
                [restaurant_id],
            ).fetchall()
    columns = [
        "priority_run_id",
        "restaurant_id",
        "review_month",
        "generated_at",
        "crawl_run_id",
        "absa_model_version",
        "scoring_config_hash",
        "status",
    ]
    return [dict(zip(columns, row, strict=True)) for row in rows]


def get_priority_run(db_path: str | Path, priority_run_id: str) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT priority_run_id, restaurant_id, review_month, generated_at,
                   crawl_run_id, absa_model_version, scoring_config_hash, status, output_json
            FROM priority_runs
            WHERE priority_run_id = ?
            """,
            [priority_run_id],
        ).fetchone()
    if row is None:
        return None
    columns = [
        "priority_run_id",
        "restaurant_id",
        "review_month",
        "generated_at",
        "crawl_run_id",
        "absa_model_version",
        "scoring_config_hash",
        "status",
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
