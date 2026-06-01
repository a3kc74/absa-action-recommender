from pathlib import Path
import sys

import typer

from absa_recommender.config import load_label_schema
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl

app = typer.Typer(help="Local ABSA aspect-to-action recommender.")


@app.command()
def recommend(
    input_path: Path = typer.Argument(
        Path("data/samples/absa_outputs.jsonl"),
        help="Path to ABSA JSONL input.",
    ),
) -> None:
    """Print flattened negative ABSA extractions from JSONL input."""
    _configure_stdout()
    schema = load_label_schema("configs/label_schema.yaml")
    reviews = load_absa_jsonl(input_path)
    extractions = flatten_reviews(reviews, schema)
    for extraction in extractions:
        if extraction.sentiment != "negative":
            continue
        typer.echo(
            f"{extraction.extraction_id} [{extraction.aspect}] "
            f"{extraction.aspect_term}: {extraction.opinion_text}"
        )


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
