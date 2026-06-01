import re
from typing import Any

from absa_recommender.prototype_matcher import match_subproblem_prototype
from absa_recommender.schemas import AspectExtraction, SubProblemPrediction
from absa_recommender.subproblem import detect_sub_problem, normalize_text


def locate_subproblem(
    extraction: AspectExtraction,
    rules: dict[str, Any],
    prototypes: dict[str, Any],
    locator_config: dict[str, Any],
) -> SubProblemPrediction:
    rule_match = detect_sub_problem(
        extraction.aspect,
        extraction.aspect_term,
        extraction.opinion_text,
        rules,
    )
    prototype_match = match_subproblem_prototype(
        extraction.aspect,
        extraction.aspect_term,
        extraction.opinion_text,
        prototypes,
    )

    thresholds = locator_config.get("thresholds", {})
    weights = locator_config.get("weights", {})
    normalized_rule_score = _normalize_rule_score(
        rule_match.score,
        thresholds.get("rule_auto_assign", 2.0),
    )
    prototype_similarity = prototype_match.similarity
    effective_model_confidence = _clamp(extraction.model_confidence or 0.0)
    locator_score = _clamp(
        weights.get("rule_score", 0.0) * normalized_rule_score
        + weights.get("prototype_similarity", 0.0) * prototype_similarity
        + weights.get("severity", 0.0) * _clamp(extraction.severity)
        + weights.get("model_confidence", 0.0) * effective_model_confidence
    )

    predicted_sub_problem_id = _choose_sub_problem_id(
        rule_match.sub_problem_id,
        normalized_rule_score,
        prototype_match.sub_problem_id,
        prototype_similarity,
    )
    sub_problem_label = _sub_problem_label(predicted_sub_problem_id, extraction.aspect, rules)
    match_type = _match_type(normalized_rule_score, prototype_similarity)

    auto_assign_threshold = _auto_assign_threshold(extraction.aspect, locator_config)
    needs_review_threshold = thresholds.get("needs_review", 0.45)
    needs_review = locator_score < auto_assign_threshold
    if locator_score < needs_review_threshold:
        predicted_sub_problem_id = _generic_sub_problem_id(extraction.aspect, locator_config)
        sub_problem_label = f"Vấn đề chung về {extraction.aspect}"
        match_type = "generic"
        needs_review = True

    return SubProblemPrediction(
        review_id=extraction.review_id,
        aspect_category=extraction.aspect,
        aspect_expression=extraction.aspect_term,
        opinion_expression=extraction.opinion_text,
        sentiment=extraction.sentiment,
        model_confidence=extraction.model_confidence,
        predicted_sub_problem_id=predicted_sub_problem_id,
        sub_problem_label=sub_problem_label,
        locator_score=locator_score,
        match_type=match_type,
        needs_review=needs_review,
        matched_patterns={
            "aspect_expression_patterns": rule_match.matched_aspect_expression_patterns,
            "opinion_expression_patterns": rule_match.matched_opinion_expression_patterns,
        },
        nearest_prototypes=prototype_match.nearest_prototype_examples,
    )


def _normalize_rule_score(rule_score: float, rule_auto_assign: float) -> float:
    if rule_auto_assign <= 0:
        return 0.0
    return _clamp(rule_score / rule_auto_assign)


def _choose_sub_problem_id(
    rule_sub_problem_id: str,
    normalized_rule_score: float,
    prototype_sub_problem_id: str | None,
    prototype_similarity: float,
) -> str:
    if prototype_sub_problem_id is not None and prototype_similarity > normalized_rule_score:
        return prototype_sub_problem_id
    return rule_sub_problem_id


def _sub_problem_label(
    sub_problem_id: str,
    aspect: str,
    rules: dict[str, Any],
) -> str:
    rule = rules.get(aspect, {}).get(sub_problem_id)
    if rule is not None:
        return rule.get("label_vi", sub_problem_id)
    if sub_problem_id.startswith("generic_"):
        return f"Vấn đề chung về {aspect}"
    return sub_problem_id


def _match_type(normalized_rule_score: float, prototype_similarity: float) -> str:
    has_rule = normalized_rule_score > 0.0
    has_prototype = prototype_similarity > 0.0
    if has_rule and has_prototype:
        return "rule+prototype"
    if has_rule:
        return "rule"
    if has_prototype:
        return "prototype"
    return "generic"


def _auto_assign_threshold(aspect: str, locator_config: dict[str, Any]) -> float:
    thresholds = locator_config.get("thresholds", {})
    if aspect in locator_config.get("high_risk_aspects", []):
        return thresholds.get("high_risk_auto_assign", thresholds.get("auto_assign", 0.70))
    return thresholds.get("auto_assign", 0.70)


def _generic_sub_problem_id(aspect: str, locator_config: dict[str, Any]) -> str:
    prefix = locator_config.get("fallback", {}).get("generic_prefix", "generic")
    return f"{prefix}_{_slugify(aspect)}_issue"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_text(text)).strip("_")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
