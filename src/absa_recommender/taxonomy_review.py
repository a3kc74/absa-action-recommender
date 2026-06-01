from pathlib import Path
from typing import Any

import yaml


def load_taxonomy_gap_report(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def save_taxonomy_gap_report(report: dict[str, Any], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as file:
        yaml.safe_dump(report, file, allow_unicode=True, sort_keys=False)


def mark_cluster_decision(
    report: dict[str, Any],
    aspect: str,
    cluster_id: str,
    decision: str,
) -> dict[str, Any]:
    for cluster in report.get(aspect, {}).get("clusters", []):
        if cluster.get("cluster_id") == cluster_id:
            cluster["review_decision"] = decision
            break
    return report


def apply_taxonomy_suggestions(
    reviewed_report_path: str | Path,
    rules_path: str | Path,
    output_path: str | Path,
) -> None:
    reviewed_report = load_taxonomy_gap_report(reviewed_report_path)
    with Path(rules_path).open("r", encoding="utf-8") as file:
        rules = yaml.safe_load(file) or {}

    for aspect, aspect_report in reviewed_report.items():
        for cluster in aspect_report.get("clusters", []):
            if cluster.get("review_decision") not in {"approved", "accept", "accepted"}:
                continue
            sub_problem_id = cluster.get("suggested_existing_sub_problem_id")
            if not sub_problem_id:
                continue
            rule = rules.setdefault(aspect, {}).setdefault(sub_problem_id, {})
            suggested_update = cluster.get("suggested_update", {})
            _append_unique(
                rule.setdefault("aspect_expression_patterns", []),
                suggested_update.get("add_aspect_expression_patterns", []),
            )
            _append_unique(
                rule.setdefault("opinion_expression_patterns", []),
                suggested_update.get("add_opinion_expression_patterns", []),
            )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        yaml.safe_dump(rules, file, allow_unicode=True, sort_keys=False)


def _append_unique(target: list, values: list) -> None:
    for value in values:
        if value not in target:
            target.append(value)
