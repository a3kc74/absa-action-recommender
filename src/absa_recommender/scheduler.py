from datetime import date


def previous_month_for_run(run_date: date) -> str:
    year = run_date.year
    month = run_date.month - 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


def priority_idempotency_key(
    restaurant_id: str,
    review_month: str,
    scoring_config_hash: str,
    absa_model_version: str,
) -> tuple[str, str, str, str]:
    return (restaurant_id, review_month, scoring_config_hash, absa_model_version)
