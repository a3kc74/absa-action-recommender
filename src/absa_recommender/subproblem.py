import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from absa_recommender.config import load_yaml
from absa_recommender.schemas import AspectExtraction, SubProblemMatch


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def load_subproblem_rules(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def detect_sub_problem(
    aspect: str,
    aspect_term: str,
    opinion_text: str,
    rules: dict[str, Any],
) -> SubProblemMatch:
    best_match: SubProblemMatch | None = None
    for sub_problem_id, rule in rules.get(aspect, {}).items():
        matched_aspect_patterns = _matched_patterns(
            aspect_term,
            rule.get("aspect_expression_patterns", []),
        )
        matched_opinion_patterns = _matched_patterns(
            opinion_text,
            rule.get("opinion_expression_patterns", []),
        )
        if not matched_aspect_patterns and not matched_opinion_patterns:
            score = 0.0
        else:
            score = (
                len(matched_opinion_patterns) * 2
                + len(matched_aspect_patterns)
                + float(rule.get("priority", 0)) / 100
            )
        if score <= 0:
            continue

        match = SubProblemMatch(
            aspect=aspect,
            sub_problem_id=sub_problem_id,
            sub_problem_label=rule.get("label_vi", sub_problem_id),
            matched_aspect_expression_patterns=matched_aspect_patterns,
            matched_opinion_expression_patterns=matched_opinion_patterns,
            score=score,
        )
        if best_match is None or match.score > best_match.score:
            best_match = match

    if best_match is not None:
        return best_match

    return SubProblemMatch(
        aspect=aspect,
        sub_problem_id=f"generic_{_slugify(aspect)}_issue",
        sub_problem_label=f"Vấn đề chung về {aspect}",
        matched_aspect_expression_patterns=[],
        matched_opinion_expression_patterns=[],
        score=0.0,
    )


def group_extractions_by_subproblem(
    extractions: list[AspectExtraction],
    rules: dict[str, Any],
) -> dict[tuple[str, str, str], list[AspectExtraction]]:
    grouped: dict[tuple[str, str, str], list[AspectExtraction]] = defaultdict(list)
    for extraction in extractions:
        match = detect_sub_problem(
            extraction.aspect,
            extraction.aspect_term,
            extraction.opinion_text,
            rules,
        )
        grouped[(extraction.restaurant_id, extraction.aspect, match.sub_problem_id)].append(
            extraction
        )
    return dict(grouped)


def compute_subproblem_score(
    parent_priority_score: float,
    group_share: float,
    avg_severity: float,
    beta: float = 0.5,
) -> float:
    beta = _clamp(beta)
    combined_weight = (1.0 - beta) * _clamp(group_share) + beta * _clamp(avg_severity)
    return round(max(0.0, min(100.0, parent_priority_score)) * combined_weight, 4)


def _matched_patterns(text: str, patterns: list[str]) -> list[str]:
    normalized_text = normalize_text(text)
    return [pattern for pattern in patterns if normalize_text(pattern) in normalized_text]


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(text)).strip("_")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
