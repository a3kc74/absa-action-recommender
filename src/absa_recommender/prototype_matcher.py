from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from absa_recommender.config import load_yaml
from absa_recommender.schemas import PrototypeMatch
from absa_recommender.subproblem import normalize_text


def load_subproblem_prototypes(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def match_subproblem_prototype(
    aspect: str,
    aspect_term: str,
    opinion_text: str,
    prototypes: dict[str, Any],
    nearest_count: int = 3,
) -> PrototypeMatch:
    candidates = _prototype_candidates(aspect, prototypes)
    if not candidates:
        return PrototypeMatch(
            aspect=aspect,
            sub_problem_id=None,
            similarity=0.0,
            nearest_prototype_examples=[],
        )

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
    prototype_matrix = vectorizer.fit_transform([candidate["text"] for candidate in candidates])
    query_vector = vectorizer.transform([_matching_text(aspect_term, opinion_text)])
    similarities = (prototype_matrix @ query_vector.T).toarray().ravel()
    ranked_indexes = sorted(
        range(len(candidates)),
        key=lambda index: similarities[index],
        reverse=True,
    )
    best_index = ranked_indexes[0]

    return PrototypeMatch(
        aspect=aspect,
        sub_problem_id=candidates[best_index]["sub_problem_id"],
        similarity=float(similarities[best_index]),
        nearest_prototype_examples=[
            _prototype_example(candidates[index])
            for index in ranked_indexes[: max(1, nearest_count)]
        ],
    )


def _prototype_candidates(aspect: str, prototypes: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for sub_problem_id, config in prototypes.get(aspect, {}).items():
        for example in config.get("examples", []):
            aspect_expression = example["aspect_expression"]
            opinion_expression = example["opinion_expression"]
            candidates.append(
                {
                    "sub_problem_id": sub_problem_id,
                    "aspect_expression": aspect_expression,
                    "opinion_expression": opinion_expression,
                    "text": _matching_text(aspect_expression, opinion_expression),
                }
            )
    return candidates


def _matching_text(aspect_expression: str, opinion_expression: str) -> str:
    return normalize_text(f"{aspect_expression} | {opinion_expression}")


def _prototype_example(candidate: dict[str, str]) -> dict[str, str]:
    return {
        "sub_problem_id": candidate["sub_problem_id"],
        "aspect_expression": candidate["aspect_expression"],
        "opinion_expression": candidate["opinion_expression"],
    }
