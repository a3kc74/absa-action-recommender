from pathlib import Path

from absa_recommender.prototype_matcher import (
    load_subproblem_prototypes,
    match_subproblem_prototype,
)


PROTOTYPES = load_subproblem_prototypes(Path("configs/subproblem_prototypes.yaml"))


def test_nuoc_dung_loang_matches_bland_or_no_flavor() -> None:
    match = match_subproblem_prototype(
        "Food Quality",
        "nước dùng",
        "loãng không có vị bò",
        PROTOTYPES,
    )

    assert match.sub_problem_id == "bland_or_no_flavor"
    assert match.similarity > 0.0
    assert match.nearest_prototype_examples[0]["sub_problem_id"] == "bland_or_no_flavor"


def test_muong_vet_den_matches_dirty_tableware() -> None:
    match = match_subproblem_prototype(
        "Cleanliness",
        "muỗng",
        "có vệt đen nhìn dơ",
        PROTOTYPES,
    )

    assert match.sub_problem_id == "dirty_tableware"
    assert match.similarity > 0.0


def test_menu_item_unavailable_matches_menu_item_unavailable() -> None:
    match = match_subproblem_prototype(
        "Menu",
        "menu",
        "món trên menu không còn bán",
        PROTOTYPES,
    )

    assert match.sub_problem_id == "menu_item_unavailable"
    assert match.similarity > 0.0


def test_prototype_matcher_does_not_compare_across_different_aspects() -> None:
    match = match_subproblem_prototype(
        "Food Quality",
        "menu",
        "món trên menu không còn bán",
        PROTOTYPES,
    )

    assert match.sub_problem_id != "menu_item_unavailable"
