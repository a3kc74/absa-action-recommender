from pathlib import Path

from typer.testing import CliRunner

from absa_recommender.cli import app


runner = CliRunner()
SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


def test_validate_command_exits_0() -> None:
    result = runner.invoke(app, ["validate", "--input", str(SAMPLE_PATH)])

    assert result.exit_code == 0
    assert "reviews: 3" in result.output
    assert "annotations: 7" in result.output


def test_recommend_creates_output_json(tmp_path: Path) -> None:
    output = tmp_path / "recommendations.json"

    result = runner.invoke(
        app,
        [
            "recommend",
            "--input",
            str(SAMPLE_PATH),
            "--restaurant-id",
            "res_demo",
            "--top-n",
            "5",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert "saved:" in result.output


def test_show_labels_includes_location_and_menu() -> None:
    result = runner.invoke(app, ["show-labels"])

    assert result.exit_code == 0
    assert "Location" in result.output
    assert "Menu" in result.output


def test_locate_subproblems_creates_jsonl(tmp_path: Path) -> None:
    output = tmp_path / "subproblem_predictions.jsonl"

    result = runner.invoke(
        app,
        ["locate-subproblems", "--input", str(SAMPLE_PATH), "--output", str(output)],
    )

    assert result.exit_code == 0
    assert output.exists()
    assert output.read_text(encoding="utf-8").strip()


def test_mine_taxonomy_creates_yaml_and_csv(tmp_path: Path) -> None:
    predictions = tmp_path / "subproblem_predictions.jsonl"
    report = tmp_path / "taxonomy_gap_report.yaml"
    csv = tmp_path / "unmatched_annotations.csv"
    locate_result = runner.invoke(
        app,
        ["locate-subproblems", "--input", str(SAMPLE_PATH), "--output", str(predictions)],
    )

    result = runner.invoke(
        app,
        [
            "mine-taxonomy",
            "--predictions",
            str(predictions),
            "--output-report",
            str(report),
            "--output-csv",
            str(csv),
        ],
    )

    assert locate_result.exit_code == 0
    assert result.exit_code == 0
    assert report.exists()
    assert csv.exists()


def test_evaluate_command_outputs_metrics(tmp_path: Path) -> None:
    output = tmp_path / "recommendations.json"
    recommend_result = runner.invoke(
        app,
        [
            "recommend",
            "--input",
            str(SAMPLE_PATH),
            "--restaurant-id",
            "res_demo",
            "--top-n",
            "5",
            "--output",
            str(output),
        ],
    )

    result = runner.invoke(
        app,
        [
            "evaluate",
            "--predictions",
            str(output),
            "--gold",
            "data/gold.json",
            "--k",
            "5",
        ],
    )

    assert recommend_result.exit_code == 0
    assert result.exit_code == 0
    assert "precision_at_k" in result.output
