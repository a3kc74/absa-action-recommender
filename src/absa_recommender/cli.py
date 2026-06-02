import json
import sys
from pathlib import Path
from typing import Any

import typer

from absa_recommender.config import load_label_schema
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl
from absa_recommender.recommender import generate_priority_ranking

app = typer.Typer(help="Local ABSA aspect priority engine.")


@app.command()
def validate(
    input_path: Path = typer.Option(
        Path("data/samples/absa_outputs.jsonl"),
        "--input",
        help="Path to ABSA JSONL input.",
    ),
) -> None:
    """Parse JSONL and validate labels against label_schema.yaml."""
    _configure_stdout()
    schema = load_label_schema("configs/label_schema.yaml")
    reviews = load_absa_jsonl(input_path)
    extractions = flatten_reviews(reviews, schema, strict=True)
    typer.echo(f"reviews: {len(reviews)}")
    typer.echo(f"annotations: {len(extractions)}")


@app.command("score-priority")
def score_priority(
    input_path: Path = typer.Option(
        Path("data/samples/absa_outputs.jsonl"),
        "--input",
        help="Path to ABSA JSONL input.",
    ),
    restaurant_id: str | None = typer.Option(
        None,
        "--restaurant-id",
        help="Override restaurant_id for this batch.",
    ),
    month: str | None = typer.Option(
        None,
        "--month",
        help="Review month to score, for example 2026-06.",
    ),
    top_n: int = typer.Option(5, "--top-n", min=1, help="Number of aspects."),
    output: Path = typer.Option(
        Path("out/priority.json"),
        "--output",
        help="Path to write priority JSON.",
    ),
) -> None:
    """Rank Top-N aspects to improve from ABSA JSONL."""
    _configure_stdout()
    reviews = _load_reviews_with_restaurant_override(input_path, restaurant_id)
    response = generate_priority_ranking(reviews, top_n=top_n, review_month=month)
    _write_json(output, response.model_dump(mode="json"))
    typer.echo(f"saved: {output}")
    for item in response.items:
        typer.echo(
            f"{item.rank}. {item.aspect} score={item.priority_score:.2f} "
            f"confidence={item.priority_confidence:.2f}"
        )


@app.command("run-monthly")
def run_monthly(
    input_path: Path = typer.Option(
        Path("data/samples/absa_outputs.jsonl"),
        "--input",
        help="Path to monthly ABSA JSONL input.",
    ),
    restaurant_id: str | None = typer.Option(None, "--restaurant-id"),
    month: str | None = typer.Option(None, "--month"),
    top_n: int = typer.Option(5, "--top-n", min=1),
    output: Path = typer.Option(Path("out/priority.json"), "--output"),
) -> None:
    """Run the local monthly priority step from existing ABSA annotations."""
    score_priority(input_path, restaurant_id, month, top_n, output)


@app.command("compute-stats")
def compute_stats(
    input_path: Path = typer.Option(Path("data/samples/absa_outputs.jsonl"), "--input"),
    restaurant_id: str | None = typer.Option(None, "--restaurant-id"),
    month: str | None = typer.Option(None, "--month"),
    output: Path = typer.Option(Path("out/aspect_monthly_stats.json"), "--output"),
) -> None:
    """Compute monthly aspect stats by running priority scoring and exporting item stats."""
    _configure_stdout()
    reviews = _load_reviews_with_restaurant_override(input_path, restaurant_id)
    response = generate_priority_ranking(reviews, top_n=100, review_month=month)
    rows = [
        {
            "restaurant_id": response.restaurant_id,
            "review_month": response.review_month,
            "aspect": item.aspect,
            "mention_count": item.mention_count,
            "negative_count": item.negative_count,
            "negative_rate_smoothed": item.negative_rate_smoothed,
            "severity": item.severity,
            "mention_share": item.mention_share,
            "rating_gap": item.rating_gap,
        }
        for item in response.items
    ]
    _write_json(output, rows)
    typer.echo(f"saved: {output}")


@app.command("discover-peers")
def discover_peers(restaurant_id: str, radius_meters: int = 1500) -> None:
    """Placeholder for a licensed/source-adapter peer discovery implementation."""
    _configure_stdout()
    typer.echo(
        json.dumps(
            {
                "status": "not_configured",
                "restaurant_id": restaurant_id,
                "radius_meters": radius_meters,
            },
            ensure_ascii=False,
        )
    )


@app.command("crawl-month")
def crawl_month(restaurant_id: str, month: str) -> None:
    """Placeholder for source-adapter monthly review crawling."""
    _configure_stdout()
    typer.echo(
        json.dumps(
            {"status": "not_configured", "restaurant_id": restaurant_id, "review_month": month},
            ensure_ascii=False,
        )
    )


@app.command("infer-absa")
def infer_absa(month: str) -> None:
    """Placeholder for external ABSA inference integration."""
    _configure_stdout()
    typer.echo(json.dumps({"status": "not_configured", "review_month": month}, ensure_ascii=False))


@app.command()
def backfill(restaurant_id: str, start_month: str, end_month: str) -> None:
    """Placeholder for repeated monthly runs across a month range."""
    _configure_stdout()
    typer.echo(
        json.dumps(
            {
                "status": "not_configured",
                "restaurant_id": restaurant_id,
                "start_month": start_month,
                "end_month": end_month,
            },
            ensure_ascii=False,
        )
    )


@app.command("show-labels")
def show_labels() -> None:
    """Print labels loaded from label_schema.yaml."""
    _configure_stdout()
    schema = load_label_schema("configs/label_schema.yaml")
    typer.echo("Aspects:")
    for label in schema.get("aspects", []):
        typer.echo(f"- {label}")
    typer.echo("Sentiments:")
    for label in schema.get("sentiments", []):
        typer.echo(f"- {label}")


def _load_reviews_with_restaurant_override(input_path: Path, restaurant_id: str | None):
    reviews = load_absa_jsonl(input_path)
    if restaurant_id is None:
        return reviews
    return [review.model_copy(update={"restaurant_id": restaurant_id}) for review in reviews]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
