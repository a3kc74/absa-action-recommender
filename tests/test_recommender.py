from pathlib import Path

from absa_recommender.io import load_absa_jsonl
from absa_recommender.recommender import recommend_actions


def test_load_sample_jsonl() -> None:
    records = load_absa_jsonl(Path("data/samples/absa_outputs.jsonl"))

    assert len(records) == 3
    assert records[0].review_id == "rv_001"


def test_recommends_only_negative_aspects() -> None:
    record = load_absa_jsonl(Path("data/samples/absa_outputs.jsonl"))[0]

    recommendations = recommend_actions(record)

    assert len(recommendations) == 1
    assert recommendations[0].aspect == "service"
