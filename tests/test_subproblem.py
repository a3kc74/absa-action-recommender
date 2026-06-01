from pathlib import Path

from absa_recommender.schemas import AspectExtraction
from absa_recommender.subproblem import (
    compute_subproblem_score,
    detect_sub_problem,
    group_extractions_by_subproblem,
    load_subproblem_rules,
)


RULES = load_subproblem_rules(Path("configs/subproblem_rules.yaml"))


def test_pho_bo_khong_he_dam_da_maps_to_bland_or_no_flavor() -> None:
    match = detect_sub_problem("Food Quality", "phở bò", "không hề đậm đà", RULES)

    assert match.sub_problem_id == "bland_or_no_flavor"
    assert "phở bò" in match.matched_aspect_expression_patterns
    assert "không hề đậm đà" in match.matched_opinion_expression_patterns


def test_nguoi_phuc_vu_doi_y_maps_to_inconsistent_service_response() -> None:
    match = detect_sub_problem("Service", "người phục vụ", "đổi ý", RULES)

    assert match.sub_problem_id == "inconsistent_service_response"


def test_cocktail_delay_maps_to_slow_food_or_drink_preparation() -> None:
    match = detect_sub_problem("Service", "cocktail", "mất đến nửa tiếng", RULES)

    assert match.sub_problem_id == "slow_food_or_drink_preparation"


def test_bat_dia_rat_ban_maps_to_dirty_tableware() -> None:
    match = detect_sub_problem("Cleanliness", "bát đĩa", "rất bẩn", RULES)

    assert match.sub_problem_id == "dirty_tableware"


def test_nha_hang_dat_do_maps_to_overpriced() -> None:
    match = detect_sub_problem("Price", "nhà hàng", "đắt đỏ", RULES)

    assert match.sub_problem_id == "overpriced"


def test_duong_vao_kho_tim_maps_to_hard_to_find() -> None:
    match = detect_sub_problem("Location", "đường vào", "khó tìm", RULES)

    assert match.sub_problem_id == "hard_to_find"


def test_gui_xe_khong_co_cho_maps_to_parking_issue() -> None:
    match = detect_sub_problem("Location", "gửi xe", "không có chỗ", RULES)

    assert match.sub_problem_id == "parking_issue"


def test_menu_het_mon_maps_to_menu_item_unavailable() -> None:
    match = detect_sub_problem("Menu", "menu", "hết món", RULES)

    assert match.sub_problem_id == "menu_item_unavailable"


def test_menu_khong_giong_hinh_maps_to_menu_photo_mismatch() -> None:
    match = detect_sub_problem("Menu", "menu", "không giống hình", RULES)

    assert match.sub_problem_id == "menu_photo_mismatch"


def test_unmatched_rule_returns_generic_fallback() -> None:
    match = detect_sub_problem("Ambience", "ban công", "bình thường", RULES)

    assert match.sub_problem_id == "generic_ambience_issue"
    assert match.sub_problem_label == "Vấn đề chung về Ambience"
    assert match.score == 0.0


def test_group_extractions_by_subproblem() -> None:
    extractions = [
        _extraction("rest_001", "Menu", "menu", "hết món"),
        _extraction("rest_001", "Menu", "menu", "không giống hình"),
    ]

    grouped = group_extractions_by_subproblem(extractions, RULES)

    assert ("rest_001", "Menu", "menu_item_unavailable") in grouped
    assert ("rest_001", "Menu", "menu_photo_mismatch") in grouped


def test_compute_subproblem_score_blends_share_and_severity() -> None:
    assert compute_subproblem_score(80.0, group_share=0.5, avg_severity=1.0) == 60.0


def _extraction(
    restaurant_id: str,
    aspect: str,
    aspect_term: str,
    opinion_text: str,
) -> AspectExtraction:
    return AspectExtraction(
        extraction_id=f"{restaurant_id}_{aspect_term}",
        review_id="rv_001",
        restaurant_id=restaurant_id,
        restaurant_name=None,
        aspect=aspect,
        aspect_term=aspect_term,
        opinion_text=opinion_text,
        sentiment="negative",
        severity=0.75,
        model_confidence=0.8,
        review_text=opinion_text,
        rating=3,
        review_time=None,
    )
