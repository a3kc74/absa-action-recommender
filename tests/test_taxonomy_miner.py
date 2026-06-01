import csv
import json
from pathlib import Path

from absa_recommender.config import load_yaml
from absa_recommender.taxonomy_miner import (
    export_taxonomy_outputs,
    mine_taxonomy_gaps,
    run_taxonomy_miner,
    select_candidate_annotations,
)


TAXONOMY_CONFIG = load_yaml(Path("configs/taxonomy_miner.yaml"))
RULES = load_yaml(Path("configs/subproblem_rules.yaml"))
PROTOTYPES = load_yaml(Path("configs/subproblem_prototypes.yaml"))


def test_generic_unmatched_annotations_are_included() -> None:
    candidates = select_candidate_annotations(_predictions(), TAXONOMY_CONFIG)

    ids = {item["review_id"] for item in candidates}

    assert "generic_01" in ids


def test_weak_match_annotations_are_included() -> None:
    candidates = select_candidate_annotations(_predictions(), TAXONOMY_CONFIG)

    ids = {item["review_id"] for item in candidates}

    assert "weak_01" in ids


def test_high_risk_weak_annotations_are_included() -> None:
    candidates = select_candidate_annotations(_predictions(), TAXONOMY_CONFIG)

    ids = {item["review_id"] for item in candidates}

    assert "risk_01" in ids


def test_report_contains_representative_annotations() -> None:
    report, _ = mine_taxonomy_gaps(_predictions(), RULES, PROTOTYPES, TAXONOMY_CONFIG)

    first_cluster = report["Menu"]["clusters"][0]

    assert first_cluster["representative_annotations"]
    assert "opinion_expression" in first_cluster["representative_annotations"][0]


def test_report_does_not_contain_field_named_evidence() -> None:
    report, _ = mine_taxonomy_gaps(_predictions(), RULES, PROTOTYPES, TAXONOMY_CONFIG)

    assert "evidence" not in json.dumps(report, ensure_ascii=False)


def test_csv_contains_opinion_expression_column(tmp_path: Path) -> None:
    report, candidates = mine_taxonomy_gaps(_predictions(), RULES, PROTOTYPES, TAXONOMY_CONFIG)

    _, csv_path = export_taxonomy_outputs(report, candidates, tmp_path)

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        assert "opinion_expression" in (reader.fieldnames or [])


def test_run_taxonomy_miner_writes_outputs(tmp_path: Path) -> None:
    predictions_path = tmp_path / "subproblem_predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as file:
        for prediction in _predictions():
            file.write(json.dumps(prediction, ensure_ascii=False) + "\n")

    report, report_path, csv_path = run_taxonomy_miner(predictions_path, out_dir=tmp_path)

    assert report
    assert report_path.exists()
    assert csv_path.exists()


def _predictions() -> list[dict]:
    return [
        {
            "review_id": "generic_01",
            "aspect_category": "Menu",
            "aspect_expression": "combo",
            "opinion_expression": "không rõ gồm món gì",
            "sentiment": "negative",
            "model_confidence": 0.80,
            "predicted_sub_problem_id": "generic_menu_issue",
            "sub_problem_label": "Vấn đề chung về Menu",
            "locator_score": 0.30,
            "match_type": "generic",
            "needs_review": True,
            "severity": 0.75,
        },
        {
            "review_id": "weak_01",
            "aspect_category": "Location",
            "aspect_expression": "đường vào",
            "opinion_expression": "đi lòng vòng khó tìm",
            "sentiment": "negative",
            "model_confidence": 0.80,
            "predicted_sub_problem_id": "hard_to_find",
            "sub_problem_label": "Quán khó tìm",
            "locator_score": 0.40,
            "match_type": "rule",
            "needs_review": False,
            "severity": 0.75,
        },
        {
            "review_id": "risk_01",
            "aspect_category": "Cleanliness",
            "aspect_expression": "ly",
            "opinion_expression": "có vệt đen",
            "sentiment": "negative",
            "model_confidence": 0.85,
            "predicted_sub_problem_id": "dirty_tableware",
            "sub_problem_label": "Dụng cụ ăn uống bẩn",
            "locator_score": 0.65,
            "match_type": "prototype",
            "needs_review": False,
            "severity": 0.90,
        },
        {
            "review_id": "positive_01",
            "aspect_category": "Service",
            "aspect_expression": "nhân viên",
            "opinion_expression": "thân thiện",
            "sentiment": "positive",
            "model_confidence": 0.90,
            "predicted_sub_problem_id": "generic_service_issue",
            "locator_score": 0.20,
            "needs_review": True,
        },
    ]
