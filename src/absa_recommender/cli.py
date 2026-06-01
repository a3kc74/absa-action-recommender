import json
import sys
from pathlib import Path
from typing import Any

import typer

from absa_recommender.config import load_label_schema, load_yaml
from absa_recommender.evaluation import evaluate_recommendation_file
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl
from absa_recommender.prototype_matcher import load_subproblem_prototypes
from absa_recommender.recommender import generate_recommendations
from absa_recommender.subproblem import load_subproblem_rules
from absa_recommender.subproblem_locator import locate_subproblem
from absa_recommender.taxonomy_miner import (
    export_taxonomy_outputs,
    load_subproblem_predictions,
    mine_taxonomy_gaps,
)
from absa_recommender.taxonomy_review import apply_taxonomy_suggestions

app = typer.Typer(help="Local ABSA aspect-to-action recommender.")


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


@app.command()
def recommend(
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
    top_n: int = typer.Option(5, "--top-n", min=1, help="Number of recommendations."),
    output: Path = typer.Option(
        Path("out/recommendations.json"),
        "--output",
        help="Path to write recommendation JSON.",
    ),
) -> None:
    """Generate recommendations and save JSON output."""
    _configure_stdout()
    reviews = _load_reviews_with_restaurant_override(input_path, restaurant_id)
    response = generate_recommendations(reviews, top_n=top_n)
    _write_json(output, response.model_dump(mode="json"))
    typer.echo(f"saved: {output}")
    for item in response.recommendations:
        typer.echo(
            f"{item.rank}. {item.aspect} / {item.sub_problem_id} "
            f"score={item.priority_score:.2f}"
        )


@app.command("inspect-subproblems")
def inspect_subproblems(
    input_path: Path = typer.Option(
        Path("data/samples/absa_outputs.jsonl"),
        "--input",
        help="Path to ABSA JSONL input.",
    ),
) -> None:
    """Print located sub-problems for negative annotations."""
    _configure_stdout()
    for prediction in _locate_negative_predictions(input_path):
        typer.echo(
            f"{prediction['aspect_category']}\t{prediction['aspect_expression']}\t"
            f"{prediction['opinion_expression']}\t{prediction['predicted_sub_problem_id']}"
        )


@app.command("locate-subproblems")
def locate_subproblems(
    input_path: Path = typer.Option(
        Path("data/samples/absa_outputs.jsonl"),
        "--input",
        help="Path to ABSA JSONL input.",
    ),
    output: Path = typer.Option(
        Path("out/subproblem_predictions.jsonl"),
        "--output",
        help="Path to write sub-problem prediction JSONL.",
    ),
) -> None:
    """Run subproblem locator for each negative annotation and save JSONL."""
    _configure_stdout()
    predictions = _locate_negative_predictions(input_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for prediction in predictions:
            file.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    typer.echo(f"saved: {output}")
    typer.echo(f"predictions: {len(predictions)}")


@app.command("mine-taxonomy")
def mine_taxonomy(
    predictions: Path = typer.Option(
        Path("out/subproblem_predictions.jsonl"),
        "--predictions",
        help="Path to sub-problem prediction JSONL.",
    ),
    output_report: Path = typer.Option(
        Path("out/taxonomy_gap_report.yaml"),
        "--output-report",
        help="Path to write taxonomy gap report YAML.",
    ),
    output_csv: Path = typer.Option(
        Path("out/unmatched_annotations.csv"),
        "--output-csv",
        help="Path to write unmatched annotations CSV.",
    ),
) -> None:
    """Run taxonomy miner on weak, generic, or needs-review annotations."""
    _configure_stdout()
    report, candidates = mine_taxonomy_gaps(
        load_subproblem_predictions(predictions),
        load_subproblem_rules("configs/subproblem_rules.yaml"),
        load_subproblem_prototypes("configs/subproblem_prototypes.yaml"),
        load_yaml("configs/taxonomy_miner.yaml"),
    )
    temp_dir = output_report.parent
    report_path, csv_path = export_taxonomy_outputs(report, candidates, temp_dir)
    _move_if_needed(report_path, output_report)
    _move_if_needed(csv_path, output_csv)
    typer.echo(f"report: {output_report}")
    typer.echo(f"csv: {output_csv}")
    typer.echo(f"candidates: {len(candidates)}")


@app.command("apply-taxonomy-suggestions")
def apply_taxonomy_suggestions_command(
    reviewed_report: Path = typer.Option(
        Path("out/taxonomy_gap_report.yaml"),
        "--reviewed-report",
        help="Reviewed taxonomy report YAML.",
    ),
    rules: Path = typer.Option(
        Path("configs/subproblem_rules.yaml"),
        "--rules",
        help="Original subproblem rules YAML.",
    ),
    output: Path = typer.Option(
        Path("configs/subproblem_rules.updated.yaml"),
        "--output",
        help="Path to write updated rules YAML.",
    ),
) -> None:
    """Apply approved taxonomy suggestions without overwriting the original rules file."""
    _configure_stdout()
    apply_taxonomy_suggestions(reviewed_report, rules, output)
    typer.echo(f"saved: {output}")


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


@app.command()
def evaluate(
    predictions: Path = typer.Option(
        Path("out/recommendations.json"),
        "--predictions",
        help="Recommendation JSON output.",
    ),
    gold: Path = typer.Option(
        Path("data/gold.json"),
        "--gold",
        help="Gold relevance JSON.",
    ),
    k: int = typer.Option(5, "--k", min=1, help="Evaluation cutoff."),
) -> None:
    """Evaluate recommendation output against a simple gold file."""
    _configure_stdout()
    with predictions.open("r", encoding="utf-8") as file:
        predictions_payload = json.load(file)
    with gold.open("r", encoding="utf-8") as file:
        gold_payload = json.load(file)
    metrics = evaluate_recommendation_file(predictions_payload, gold_payload, k)
    typer.echo(json.dumps(metrics, ensure_ascii=False, indent=2))


def _locate_negative_predictions(input_path: Path) -> list[dict[str, Any]]:
    schema = load_label_schema("configs/label_schema.yaml")
    rules = load_subproblem_rules("configs/subproblem_rules.yaml")
    prototypes = load_subproblem_prototypes("configs/subproblem_prototypes.yaml")
    locator_config = load_yaml("configs/locator.yaml")
    reviews = load_absa_jsonl(input_path)
    extractions = flatten_reviews(reviews, schema, strict=True)
    predictions: list[dict[str, Any]] = []
    for extraction in extractions:
        if extraction.sentiment != "negative":
            continue
        prediction = locate_subproblem(extraction, rules, prototypes, locator_config)
        payload = prediction.model_dump(mode="json")
        payload["severity"] = extraction.severity
        predictions.append(payload)
    return predictions


def _load_reviews_with_restaurant_override(input_path: Path, restaurant_id: str | None):
    reviews = load_absa_jsonl(input_path)
    if restaurant_id is None:
        return reviews
    return [review.model_copy(update={"restaurant_id": restaurant_id}) for review in reviews]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _move_if_needed(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        return
    source.replace(destination)


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
