import json
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from absa_recommender.config import load_label_schema, load_yaml
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl
from absa_recommender.prototype_matcher import load_subproblem_prototypes
from absa_recommender.recommender import generate_recommendations
from absa_recommender.schemas import ABSAReview
from absa_recommender.subproblem import load_subproblem_rules
from absa_recommender.subproblem_locator import locate_subproblem
from absa_recommender.taxonomy_miner import mine_taxonomy_gaps


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


st.set_page_config(page_title="ABSA Action Recommender", layout="wide")
st.title("ABSA Action Recommender")


def main() -> None:
    label_schema = load_label_schema("configs/label_schema.yaml")
    st.sidebar.header("Input")
    uploaded_file = st.sidebar.file_uploader("ABSA JSONL", type=["jsonl", "json"])
    default_restaurant_id = st.sidebar.text_input("Default restaurant_id", value="unknown")
    top_n = st.sidebar.slider("Top N", min_value=1, max_value=20, value=5)
    generate = st.sidebar.button("Generate recommendations", type="primary")

    reviews = _load_reviews(uploaded_file)
    _show_labels(label_schema)

    if not generate:
        st.info("Upload a JSONL file or use the bundled sample, then generate recommendations.")
        st.caption(f"Loaded reviews: {len(reviews)}")
        return

    response = generate_recommendations(
        reviews,
        top_n=top_n,
        default_restaurant_id=default_restaurant_id,
    )
    predictions = _locate_predictions(reviews, label_schema, default_restaurant_id)
    report, _ = mine_taxonomy_gaps(
        predictions,
        load_subproblem_rules("configs/subproblem_rules.yaml"),
        load_subproblem_prototypes("configs/subproblem_prototypes.yaml"),
        load_yaml("configs/taxonomy_miner.yaml"),
    )

    tab_recommendations, tab_locator, tab_taxonomy = st.tabs(
        ["Recommendations", "Sub-problem Locator", "Taxonomy Gaps"]
    )
    with tab_recommendations:
        _show_recommendations(response.recommendations)
    with tab_locator:
        _show_locator_predictions(predictions)
    with tab_taxonomy:
        _show_taxonomy_report(report)


def _load_reviews(uploaded_file) -> list[ABSAReview]:
    if uploaded_file is None:
        return load_absa_jsonl(SAMPLE_PATH)

    text = uploaded_file.getvalue().decode("utf-8")
    reviews = []
    for line in text.splitlines():
        if line.strip():
            reviews.append(ABSAReview.model_validate(json.loads(line)))
    return reviews


def _show_labels(label_schema: dict[str, Any]) -> None:
    with st.expander("Configured labels", expanded=True):
        col_aspects, col_sentiments = st.columns(2)
        with col_aspects:
            st.subheader("Aspects")
            st.write(", ".join(label_schema.get("aspects", [])))
        with col_sentiments:
            st.subheader("Sentiments")
            st.write(", ".join(label_schema.get("sentiments", [])))


def _locate_predictions(
    reviews: list[ABSAReview],
    label_schema: dict[str, Any],
    default_restaurant_id: str,
) -> list[dict[str, Any]]:
    extractions = flatten_reviews(
        reviews,
        label_schema,
        default_restaurant_id=default_restaurant_id,
        strict=True,
    )
    rules = load_subproblem_rules("configs/subproblem_rules.yaml")
    prototypes = load_subproblem_prototypes("configs/subproblem_prototypes.yaml")
    locator_config = load_yaml("configs/locator.yaml")
    predictions: list[dict[str, Any]] = []
    for extraction in extractions:
        if extraction.sentiment != "negative":
            continue
        prediction = locate_subproblem(extraction, rules, prototypes, locator_config)
        payload = prediction.model_dump(mode="json")
        payload["severity"] = extraction.severity
        predictions.append(payload)
    return predictions


def _show_recommendations(recommendations) -> None:
    if not recommendations:
        st.warning("No recommendations generated.")
        return

    for item in recommendations:
        with st.container(border=True):
            header_cols = st.columns([1, 2, 3, 2, 2, 2])
            header_cols[0].metric("Rank", item.rank)
            header_cols[1].write(f"**{item.aspect}**")
            header_cols[2].write(item.sub_problem_label)
            header_cols[3].metric("Priority", f"{item.priority_score:.2f}")
            header_cols[4].metric("Confidence", f"{item.confidence:.2f}")
            header_cols[5].metric("Severity", f"{item.severity:.2f}")

            st.write("**Opinion examples**")
            for example in item.opinion_examples:
                st.write(f"- {example}")

            action_col, kpi_col = st.columns(2)
            with action_col:
                st.write("**Recommended actions**")
                for action in item.recommended_actions:
                    st.write(f"- {action}")
            with kpi_col:
                st.write("**Monitoring KPIs**")
                for kpi in item.monitoring_kpis:
                    st.write(f"- `{kpi}`")

            st.write("**Component scores**")
            st.dataframe(
                [
                    {"component": key, "score": value}
                    for key, value in item.component_scores.items()
                ],
                use_container_width=True,
                hide_index=True,
            )


def _show_locator_predictions(predictions: list[dict[str, Any]]) -> None:
    if not predictions:
        st.warning("No negative annotations to locate.")
        return

    rows = [
        {
            "aspect_category": item["aspect_category"],
            "aspect_expression": item["aspect_expression"],
            "opinion_expression": item["opinion_expression"],
            "predicted_sub_problem_id": item["predicted_sub_problem_id"],
            "locator_score": item["locator_score"],
            "match_type": item["match_type"],
            "needs_review": item["needs_review"],
        }
        for item in predictions
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _show_taxonomy_report(report: dict[str, Any]) -> None:
    if not report:
        st.info("No weak, generic, or needs-review annotations found.")
        return

    yaml_text = yaml.safe_dump(report, allow_unicode=True, sort_keys=False)
    st.download_button(
        "Export taxonomy_gap_report.yaml",
        data=yaml_text,
        file_name="taxonomy_gap_report.yaml",
        mime="application/x-yaml",
    )

    for aspect, aspect_report in report.items():
        st.subheader(aspect)
        for cluster in aspect_report.get("clusters", []):
            with st.expander(
                f"{cluster['cluster_id']} · size {cluster['cluster_size']}",
                expanded=True,
            ):
                col_left, col_right = st.columns(2)
                with col_left:
                    st.write("**Top aspect expressions**")
                    st.write(", ".join(cluster.get("top_aspect_expressions", [])))
                with col_right:
                    st.write("**Top opinion phrases**")
                    st.write(", ".join(cluster.get("top_opinion_phrases", [])))

                st.write("**Representative annotations**")
                st.dataframe(
                    cluster.get("representative_annotations", []),
                    use_container_width=True,
                    hide_index=True,
                )


if __name__ == "__main__":
    main()
