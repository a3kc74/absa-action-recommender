from pathlib import Path

import typer

from absa_recommender.io import load_absa_jsonl
from absa_recommender.recommender import recommend_actions

app = typer.Typer(help="Local ABSA aspect-to-action recommender.")


@app.command()
def recommend(
    input_path: Path = typer.Argument(
        Path("data/samples/absa_outputs.jsonl"),
        help="Path to ABSA JSONL input.",
    ),
) -> None:
    """Print simple action recommendations for negative aspects."""
    for record in load_absa_jsonl(input_path):
        typer.echo(f"{record.review_id} ({record.restaurant_id})")
        recommendations = recommend_actions(record)
        if not recommendations:
            typer.echo("  No negative aspects found.")
            continue
        for item in recommendations:
            typer.echo(f"  [{item.priority}] {item.aspect}: {item.action} Reason: {item.reason}")
