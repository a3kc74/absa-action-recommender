import json
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


def test_score_priority_creates_output_json(tmp_path: Path) -> None:
    output = tmp_path / "priority.json"

    result = runner.invoke(
        app,
        [
            "score-priority",
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

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.exit_code == 0
    assert output.exists()
    assert payload["items"]
    assert "saved:" in result.output


def test_placeholder_source_commands_exit_0() -> None:
    assert runner.invoke(app, ["discover-peers", "res_demo"]).exit_code == 0
    assert runner.invoke(app, ["crawl-month", "res_demo", "2026-06"]).exit_code == 0
    assert runner.invoke(app, ["infer-absa", "2026-06"]).exit_code == 0
    assert runner.invoke(app, ["backfill", "res_demo", "2026-01", "2026-06"]).exit_code == 0


def test_show_labels_includes_location_and_menu() -> None:
    result = runner.invoke(app, ["show-labels"])

    assert result.exit_code == 0
    assert "Location" in result.output
    assert "Menu" in result.output
