from datetime import datetime, timezone
from typing import Any


def build_crawl_run(
    source: str,
    target_month: str,
    area_id: str,
    restaurants: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source": source,
        "target_month": target_month,
        "area_id": area_id,
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "status": "created",
        "num_restaurants": len(restaurants),
        "num_reviews_fetched": 0,
        "num_reviews_inserted": 0,
        "num_duplicates": 0,
        "error_message": None,
    }
