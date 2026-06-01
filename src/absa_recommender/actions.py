from pathlib import Path
from typing import Any

from absa_recommender.config import load_yaml
from absa_recommender.schemas import ActionRecommendation


def load_action_catalog(path: str | Path) -> dict[str, Any]:
    return load_yaml(path)


def get_actions(
    aspect: str,
    sub_problem_id: str,
    catalog: dict[str, Any],
) -> ActionRecommendation:
    aspect_catalog = catalog.get(aspect)
    selected_aspect = aspect
    if aspect_catalog is None:
        aspect_catalog = catalog["Unknown"]
        selected_aspect = "Unknown"

    selected_sub_problem_id = sub_problem_id
    action_config = aspect_catalog.get(sub_problem_id)
    if action_config is None:
        selected_sub_problem_id, action_config = _generic_action(aspect_catalog)

    return ActionRecommendation(
        aspect=selected_aspect,
        sub_problem_id=selected_sub_problem_id,
        actions=list(action_config.get("actions", [])),
        kpis=list(action_config.get("kpis", [])),
    )


def _generic_action(aspect_catalog: dict[str, Any]) -> tuple[str, dict[str, list[str]]]:
    for sub_problem_id, action_config in aspect_catalog.items():
        if sub_problem_id.startswith("generic_"):
            return sub_problem_id, action_config
    raise ValueError("Action catalog aspect must define a generic fallback action.")
