from pathlib import Path

from absa_recommender.config import load_yaml
from absa_recommender.prototype_matcher import load_subproblem_prototypes
from absa_recommender.schemas import AspectExtraction, SubProblemPrediction
from absa_recommender.subproblem import load_subproblem_rules
from absa_recommender.subproblem_locator import locate_subproblem


RULES = load_subproblem_rules(Path("configs/subproblem_rules.yaml"))
PROTOTYPES = load_subproblem_prototypes(Path("configs/subproblem_prototypes.yaml"))
LOCATOR_CONFIG = load_yaml(Path("configs/locator.yaml"))


def test_exact_rule_match_auto_assigns() -> None:
    prediction = locate_subproblem(
        _extraction("Food Quality", "phở bò", "không hề đậm đà", severity=0.9),
        RULES,
        PROTOTYPES,
        LOCATOR_CONFIG,
    )

    assert prediction.predicted_sub_problem_id == "bland_or_no_flavor"
    assert prediction.needs_review is False
    assert prediction.locator_score >= LOCATOR_CONFIG["thresholds"]["auto_assign"]
    assert "rule" in prediction.match_type


def test_prototype_match_works_when_no_exact_rule_exists() -> None:
    config = _locator_config(needs_review=0.30)
    prediction = locate_subproblem(
        _extraction("Food Quality", "nước lèo", "loãng vị bò yếu", severity=0.75),
        {},
        PROTOTYPES,
        config,
    )

    assert prediction.predicted_sub_problem_id == "bland_or_no_flavor"
    assert prediction.match_type == "prototype"
    assert prediction.nearest_prototypes


def test_weak_match_goes_to_needs_review() -> None:
    prediction = locate_subproblem(
        _extraction("Location", "đường vào", "khó tìm", severity=0.75, model_confidence=0.1),
        RULES,
        PROTOTYPES,
        _locator_config(auto_assign=0.95, needs_review=0.45),
    )

    assert prediction.predicted_sub_problem_id == "hard_to_find"
    assert prediction.needs_review is True
    assert prediction.locator_score >= 0.45


def test_generic_unmatched_annotation_goes_to_generic_issue() -> None:
    prediction = locate_subproblem(
        _extraction("Ambience", "ban công", "bình thường", severity=0.0, model_confidence=0.0),
        RULES,
        PROTOTYPES,
        LOCATOR_CONFIG,
    )

    assert prediction.predicted_sub_problem_id == "generic_ambience_issue"
    assert prediction.needs_review is True
    assert prediction.match_type == "generic"


def test_output_uses_opinion_expression_not_evidence() -> None:
    prediction = locate_subproblem(
        _extraction("Menu", "menu", "hết món", severity=0.9),
        RULES,
        PROTOTYPES,
        LOCATOR_CONFIG,
    )

    assert isinstance(prediction, SubProblemPrediction)
    assert prediction.opinion_expression == "hết món"
    assert "evidence" not in SubProblemPrediction.model_fields


def _extraction(
    aspect: str,
    aspect_term: str,
    opinion_text: str,
    severity: float,
    model_confidence: float = 0.9,
) -> AspectExtraction:
    return AspectExtraction(
        extraction_id="rv_001_0",
        review_id="rv_001",
        restaurant_id="rest_001",
        restaurant_name=None,
        aspect=aspect,
        aspect_term=aspect_term,
        opinion_text=opinion_text,
        sentiment="negative",
        severity=severity,
        model_confidence=model_confidence,
        review_text=opinion_text,
        rating=3,
        review_time=None,
    )


def _locator_config(
    auto_assign: float | None = None,
    needs_review: float | None = None,
) -> dict:
    config = {
        "thresholds": dict(LOCATOR_CONFIG["thresholds"]),
        "weights": dict(LOCATOR_CONFIG["weights"]),
        "high_risk_aspects": list(LOCATOR_CONFIG["high_risk_aspects"]),
        "fallback": dict(LOCATOR_CONFIG["fallback"]),
    }
    if auto_assign is not None:
        config["thresholds"]["auto_assign"] = auto_assign
    if needs_review is not None:
        config["thresholds"]["needs_review"] = needs_review
    return config
