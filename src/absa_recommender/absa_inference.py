from typing import Any, Protocol

from absa_recommender.schemas import ABSAReview


class ABSAInferenceAdapter(Protocol):
    model_version: str

    def infer(self, reviews: list[dict[str, Any]]) -> list[ABSAReview]:
        ...


class ExternalABSAInferenceNotConfigured(RuntimeError):
    pass


def infer_absa_with_adapter(
    reviews: list[dict[str, Any]],
    adapter: ABSAInferenceAdapter | None = None,
) -> list[ABSAReview]:
    if adapter is None:
        raise ExternalABSAInferenceNotConfigured(
            "Configure an ABSAInferenceAdapter before running inference."
        )
    return adapter.infer(reviews)
