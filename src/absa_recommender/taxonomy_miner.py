import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from absa_recommender.config import load_yaml
from absa_recommender.phrase_miner import cluster_text, top_opinion_phrases, top_values


DEFAULT_HIGH_RISK_ASPECTS = {"Food Safety", "Cleanliness"}


def load_subproblem_predictions(path: str | Path) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                predictions.append(json.loads(line))
    return predictions


def select_candidate_annotations(
    predictions: list[dict[str, Any]],
    taxonomy_config: dict[str, Any],
    high_risk_aspects: set[str] | None = None,
) -> list[dict[str, Any]]:
    candidate_config = taxonomy_config.get("candidate_filter", {})
    weak_threshold = float(candidate_config.get("weak_score_threshold", 0.45))
    high_risk_threshold = float(candidate_config.get("high_risk_score_threshold", 0.70))
    only_negative = bool(candidate_config.get("only_negative", True))
    include_generic = bool(candidate_config.get("include_generic", True))
    include_needs_review = bool(candidate_config.get("include_needs_review", True))
    high_risk = high_risk_aspects or DEFAULT_HIGH_RISK_ASPECTS

    candidates = []
    for prediction in predictions:
        if only_negative and prediction.get("sentiment") != "negative":
            continue
        locator_score = float(prediction.get("locator_score", 0.0))
        sub_problem_id = str(prediction.get("predicted_sub_problem_id", ""))
        aspect = prediction.get("aspect_category")
        is_candidate = (
            (include_generic and sub_problem_id.startswith("generic_"))
            or locator_score < weak_threshold
            or (include_needs_review and bool(prediction.get("needs_review", False)))
            or (aspect in high_risk and locator_score < high_risk_threshold)
        )
        if is_candidate:
            candidates.append(prediction)
    return candidates


def mine_taxonomy_gaps(
    predictions: list[dict[str, Any]],
    subproblem_rules: dict[str, Any],
    subproblem_prototypes: dict[str, Any],
    taxonomy_config: dict[str, Any],
    high_risk_aspects: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = select_candidate_annotations(predictions, taxonomy_config, high_risk_aspects)
    grouped = _group_by_aspect(candidates)
    report: dict[str, Any] = {}
    for aspect, records in grouped.items():
        report[aspect] = {
            "clusters": _cluster_aspect_records(
                aspect,
                records,
                subproblem_rules,
                subproblem_prototypes,
                taxonomy_config,
            )
        }
    return report, candidates


def export_taxonomy_outputs(
    report: dict[str, Any],
    candidates: list[dict[str, Any]],
    out_dir: str | Path = "out",
) -> tuple[Path, Path]:
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "taxonomy_gap_report.yaml"
    csv_path = output_dir / "unmatched_annotations.csv"

    with report_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(report, file, allow_unicode=True, sort_keys=False)

    fields = [
        "review_id",
        "aspect_category",
        "aspect_expression",
        "opinion_expression",
        "sentiment",
        "model_confidence",
        "current_sub_problem_id",
        "locator_score",
        "cluster_id",
    ]
    cluster_lookup = _cluster_lookup(report)
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            key = _candidate_key(candidate)
            writer.writerow(
                {
                    "review_id": candidate.get("review_id"),
                    "aspect_category": candidate.get("aspect_category"),
                    "aspect_expression": candidate.get("aspect_expression"),
                    "opinion_expression": candidate.get("opinion_expression"),
                    "sentiment": candidate.get("sentiment"),
                    "model_confidence": candidate.get("model_confidence"),
                    "current_sub_problem_id": candidate.get("predicted_sub_problem_id"),
                    "locator_score": candidate.get("locator_score"),
                    "cluster_id": cluster_lookup.get(key),
                }
            )
    return report_path, csv_path


def run_taxonomy_miner(
    predictions_path: str | Path,
    subproblem_rules_path: str | Path = "configs/subproblem_rules.yaml",
    subproblem_prototypes_path: str | Path = "configs/subproblem_prototypes.yaml",
    taxonomy_config_path: str | Path = "configs/taxonomy_miner.yaml",
    out_dir: str | Path = "out",
) -> tuple[dict[str, Any], Path, Path]:
    predictions = load_subproblem_predictions(predictions_path)
    report, candidates = mine_taxonomy_gaps(
        predictions,
        load_yaml(subproblem_rules_path),
        load_yaml(subproblem_prototypes_path),
        load_yaml(taxonomy_config_path),
    )
    report_path, csv_path = export_taxonomy_outputs(report, candidates, out_dir)
    return report, report_path, csv_path


def _cluster_aspect_records(
    aspect: str,
    records: list[dict[str, Any]],
    subproblem_rules: dict[str, Any],
    subproblem_prototypes: dict[str, Any],
    taxonomy_config: dict[str, Any],
) -> list[dict[str, Any]]:
    labels = _cluster_labels(records, taxonomy_config)
    records_by_cluster: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record, label in zip(records, labels, strict=True):
        records_by_cluster[label].append(record)

    clusters = []
    for index, (_, cluster_records) in enumerate(sorted(records_by_cluster.items()), start=1):
        cluster_id = f"{aspect.replace(' ', '_')}_{index:02d}"
        suggested_id = _suggest_existing_subproblem_id(
            cluster_records,
            subproblem_rules.get(aspect, {}),
            subproblem_prototypes.get(aspect, {}),
        )
        clusters.append(
            {
                "cluster_id": cluster_id,
                "cluster_size": len(cluster_records),
                "avg_severity": _mean(
                    [float(record.get("severity", 0.0)) for record in cluster_records]
                ),
                "top_aspect_expressions": top_values(
                    cluster_records,
                    "aspect_expression",
                    taxonomy_config.get("reporting", {}).get("top_phrases_per_cluster", 8),
                ),
                "top_opinion_phrases": top_opinion_phrases(
                    cluster_records,
                    taxonomy_config.get("reporting", {}).get("top_phrases_per_cluster", 8),
                ),
                "representative_annotations": _representative_annotations(
                    cluster_records,
                    taxonomy_config.get("reporting", {}).get(
                        "representative_annotations_per_cluster", 5
                    ),
                ),
                "current_prediction_distribution": dict(
                    Counter(
                        record.get("predicted_sub_problem_id", "unknown")
                        for record in cluster_records
                    )
                ),
                "suggested_existing_sub_problem_id": suggested_id,
                "suggested_update": {
                    "add_aspect_expression_patterns": top_values(
                        cluster_records,
                        "aspect_expression",
                        5,
                    ),
                    "add_opinion_expression_patterns": top_opinion_phrases(cluster_records, 5),
                },
                "needs_new_action": suggested_id is None,
                "review_decision": None,
            }
        )
    return clusters


def _cluster_labels(records: list[dict[str, Any]], taxonomy_config: dict[str, Any]) -> list[int]:
    if len(records) <= 1:
        return [0 for _ in records]
    texts = [
        cluster_text(record.get("aspect_expression", ""), record.get("opinion_expression", ""))
        for record in records
    ]
    vectorizer_config = taxonomy_config.get("vectorizer", {})
    min_df = min(int(vectorizer_config.get("min_df", 2)), len(records))
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=tuple(vectorizer_config.get("char_ngram_range", [3, 5])),
        min_df=max(1, min_df),
        max_df=vectorizer_config.get("max_df", 0.90),
    )
    matrix = vectorizer.fit_transform(texts)
    clustering_config = taxonomy_config.get("clustering", {})
    model = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=float(clustering_config.get("distance_threshold", 0.55)),
    )
    return list(model.fit_predict(matrix.toarray()))


def _representative_annotations(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "review_id": record.get("review_id"),
            "aspect_expression": record.get("aspect_expression"),
            "opinion_expression": record.get("opinion_expression"),
        }
        for record in records[:limit]
    ]


def _suggest_existing_subproblem_id(
    records: list[dict[str, Any]],
    aspect_rules: dict[str, Any],
    aspect_prototypes: dict[str, Any],
) -> str | None:
    distribution = Counter(
        record.get("predicted_sub_problem_id")
        for record in records
        if not str(record.get("predicted_sub_problem_id", "")).startswith("generic_")
    )
    if distribution:
        return distribution.most_common(1)[0][0]
    known_ids = set(aspect_rules) | set(aspect_prototypes)
    return sorted(known_ids)[0] if len(known_ids) == 1 else None


def _group_by_aspect(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record.get("aspect_category", "Unknown")].append(record)
    return dict(grouped)


def _cluster_lookup(report: dict[str, Any]) -> dict[tuple[Any, Any, Any], str]:
    lookup = {}
    for aspect_report in report.values():
        for cluster in aspect_report.get("clusters", []):
            for annotation in cluster.get("representative_annotations", []):
                lookup[_candidate_key(annotation)] = cluster["cluster_id"]
    return lookup


def _candidate_key(record: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (
        record.get("review_id"),
        record.get("aspect_expression"),
        record.get("opinion_expression"),
    )


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
