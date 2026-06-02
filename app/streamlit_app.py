import json
from pathlib import Path
from typing import Any

import streamlit as st

from absa_recommender.aggregation import aggregate_aspect_stats
from absa_recommender.config import load_label_schema
from absa_recommender.config import load_yaml
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl
from absa_recommender.recommender import generate_priority_ranking
from absa_recommender.schemas import ABSAReview, PriorityResponse
from absa_recommender.scoring import (
    compute_global_negative_rate_by_aspect,
    smoothed_negative_rate,
)


SAMPLE_PATH = Path("data/samples/absa_outputs.jsonl")


st.set_page_config(page_title="ABSA Aspect Priority Engine", layout="wide")
st.title("ABSA Aspect Priority Engine")


def main() -> None:
    label_schema = load_label_schema("configs/label_schema.yaml")
    st.sidebar.header("Input")
    uploaded_file = st.sidebar.file_uploader("ABSA JSONL", type=["jsonl", "json"])
    default_restaurant_id = st.sidebar.text_input("Default restaurant_id", value="unknown")
    review_month = st.sidebar.text_input("Review month", value="")
    top_n = st.sidebar.slider("Top N", min_value=1, max_value=20, value=5)
    generate = st.sidebar.button("Score priority", type="primary")

    reviews = _load_reviews(uploaded_file)
    _show_labels(label_schema)

    if not generate:
        st.info("Upload a monthly ABSA JSONL file or use the bundled sample, then score priority.")
        st.caption(f"Loaded reviews: {len(reviews)}")
        return

    month = review_month.strip() or None
    extractions = flatten_reviews(
        reviews,
        label_schema,
        default_restaurant_id=default_restaurant_id,
        strict=True,
    )
    target_reviews = _target_reviews(reviews, default_restaurant_id)
    peer_benchmarks = _peer_benchmarks(
        extractions,
        label_schema,
        default_restaurant_id,
        month,
    )
    response = generate_priority_ranking(
        target_reviews,
        top_n=top_n,
        default_restaurant_id=default_restaurant_id,
        review_month=month,
        peer_benchmarks=peer_benchmarks,
    )

    tabs = st.tabs(
        [
            "Monthly Overview",
            "Top-N Aspects",
            "Aspect Detail",
            "Peer Benchmark",
            "History",
            "Data Quality",
        ]
    )
    with tabs[0]:
        _show_overview(response, extractions)
    with tabs[1]:
        _show_priority_items(response)
    with tabs[2]:
        _show_aspect_detail(response)
    with tabs[3]:
        _show_peer_benchmark(response)
    with tabs[4]:
        _show_history(response)
    with tabs[5]:
        _show_data_quality(response, extractions)


def _load_reviews(uploaded_file) -> list[ABSAReview]:
    if uploaded_file is None:
        return load_absa_jsonl(SAMPLE_PATH)

    text = uploaded_file.getvalue().decode("utf-8")
    reviews = []
    for line in text.splitlines():
        if line.strip():
            reviews.append(ABSAReview.model_validate(json.loads(line)))
    return reviews


def _target_reviews(reviews: list[ABSAReview], target_restaurant_id: str) -> list[ABSAReview]:
    target = [review for review in reviews if (review.restaurant_id or target_restaurant_id) == target_restaurant_id]
    return target or reviews


def _peer_benchmarks(
    extractions,
    label_schema: dict[str, Any],
    target_restaurant_id: str,
    review_month: str | None,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    scoring_config = load_yaml("configs/scoring.yaml")
    month_extractions = [
        item
        for item in extractions
        if review_month is None or item.review_month == review_month
    ]
    if not month_extractions:
        return {}

    stats = aggregate_aspect_stats(month_extractions, scoring_config)
    global_rates = compute_global_negative_rate_by_aspect(month_extractions, label_schema)
    scoring = scoring_config.get("scoring", scoring_config)
    alpha = float(scoring.get("smoothing", {}).get("alpha", 10))
    stats = [
        item.model_copy(
            update={
                "negative_rate_smoothed": smoothed_negative_rate(
                    item.negative_count,
                    item.mention_count,
                    global_rates.get(item.aspect, 0.0),
                    alpha,
                )
            }
        )
        for item in stats
    ]
    target_months = {
        item.review_month
        for item in stats
        if item.restaurant_id == target_restaurant_id
    }
    target_aspects = {
        (item.review_month, item.aspect)
        for item in stats
        if item.restaurant_id == target_restaurant_id
    }
    benchmarks: dict[tuple[str, str, str], dict[str, Any]] = {}
    for month, aspect in target_aspects:
        if month not in target_months:
            continue
        peers = [
            item
            for item in stats
            if item.restaurant_id != target_restaurant_id
            and item.review_month == month
            and item.aspect == aspect
        ]
        if not peers:
            continue
        total_mentions = sum(item.mention_count for item in peers)
        total_negative = sum(item.negative_count for item in peers)
        benchmarks[(target_restaurant_id, month, aspect)] = {
            "peer_restaurant_count": len({item.restaurant_id for item in peers}),
            "peer_total_mentions": total_mentions,
            "peer_negative_rate": total_negative / total_mentions if total_mentions else 0.0,
        }
    return benchmarks


def _show_labels(label_schema: dict[str, Any]) -> None:
    with st.expander("Configured labels", expanded=False):
        col_aspects, col_sentiments = st.columns(2)
        with col_aspects:
            st.subheader("Aspects")
            st.write(", ".join(label_schema.get("aspects", [])))
        with col_sentiments:
            st.subheader("Sentiments")
            st.write(", ".join(label_schema.get("sentiments", [])))


def _show_overview(response: PriorityResponse, extractions) -> None:
    month_extractions = [
        item
        for item in extractions
        if response.review_month == "multiple" or item.review_month == response.review_month
        if response.restaurant_id == "multiple" or item.restaurant_id == response.restaurant_id
    ]
    total_reviews = len({item.review_id for item in month_extractions})
    total_annotations = len(month_extractions)
    negative_count = sum(item.sentiment == "negative" for item in month_extractions)
    ratings = [item.rating for item in month_extractions if item.rating is not None]

    cols = st.columns(4)
    cols[0].metric("Total reviews", total_reviews)
    cols[1].metric("Total ABSA annotations", total_annotations)
    cols[2].metric("Average rating", f"{_mean(ratings):.2f}" if ratings else "n/a")
    cols[3].metric(
        "Negative annotation rate",
        f"{negative_count / total_annotations:.2%}" if total_annotations else "0.00%",
    )

    st.subheader("Aspect mentions")
    st.bar_chart(
        _count_rows(month_extractions, "aspect"),
        x="label",
        y="count",
    )
    st.subheader("Sentiment distribution by aspect")
    st.dataframe(_sentiment_rows(month_extractions), use_container_width=True, hide_index=True)


def _show_priority_items(response: PriorityResponse) -> None:
    if not response.items:
        st.warning("No priority items generated.")
        return

    rows = [
        {
            "Rank": item.rank,
            "Aspect": item.aspect,
            "Priority": item.priority_score,
            "Confidence": item.priority_confidence,
            "Negative rate": item.negative_rate_smoothed,
            "Severity": item.severity,
            "Trend": item.trend_score,
            "Peer gap": item.benchmark_gap,
        }
        for item in response.items
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.bar_chart(
        [{"aspect": item.aspect, "priority_score": item.priority_score} for item in response.items],
        x="aspect",
        y="priority_score",
    )

    for item in response.items:
        with st.expander(f"#{item.rank} {item.aspect}", expanded=item.rank == 1):
            st.write("**Component scores**")
            st.dataframe(
                [
                    {"component": key, "score": value}
                    for key, value in item.component_scores.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.write("**Opinion examples**")
            for example in item.opinion_examples:
                st.write(f"- {example}")
            st.write("**Data quality flags**")
            st.write(", ".join(item.data_quality_flags) if item.data_quality_flags else "none")


def _show_aspect_detail(response: PriorityResponse) -> None:
    if not response.items:
        st.warning("No aspect detail available.")
        return
    selected = st.selectbox("Aspect", [item.aspect for item in response.items])
    item = next(row for row in response.items if row.aspect == selected)
    cols = st.columns(4)
    cols[0].metric("Rank", f"#{item.rank}")
    cols[1].metric("Priority score", f"{item.priority_score:.2f}")
    cols[2].metric("Confidence", f"{item.priority_confidence:.2f}")
    cols[3].metric("Severity", f"{item.severity:.2f}")
    st.dataframe(
        [
            {"metric": "negative_rate", "value": item.negative_rate_smoothed},
            {"metric": "mention_share", "value": item.mention_share},
            {"metric": "rating_gap", "value": item.rating_gap},
            {"metric": "trend_score", "value": item.trend_score},
            {"metric": "benchmark_gap", "value": item.benchmark_gap},
        ],
        use_container_width=True,
        hide_index=True,
    )


def _show_peer_benchmark(response: PriorityResponse) -> None:
    rows = [
        {
            "Aspect": item.aspect,
            "Target negative rate": item.negative_rate_smoothed,
            "Peer avg": item.peer_summary.peer_negative_rate,
            "Peer restaurants": item.peer_summary.peer_restaurant_count,
            "Peer gap": item.benchmark_gap,
            "Flag": item.peer_summary.peer_support_flag or "",
        }
        for item in response.items
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _show_history(response: PriorityResponse) -> None:
    st.info(
        "History uses persisted DuckDB priority_runs/priority_items snapshots when storage is wired."
    )
    st.json(
        {
            "restaurant_id": response.restaurant_id,
            "review_month": response.review_month,
            "generated_at": response.generated_at.isoformat(),
        }
    )


def _show_data_quality(response: PriorityResponse, extractions) -> None:
    target_extractions = [
        item
        for item in extractions
        if response.restaurant_id == "multiple" or item.restaurant_id == response.restaurant_id
    ]
    missing_time = sum(item.review_time is None for item in target_extractions)
    low_confidence = sum(
        item.model_confidence is not None and item.model_confidence < 0.5
        for item in target_extractions
    )
    cols = st.columns(4)
    cols[0].metric("Missing review_time", missing_time)
    cols[1].metric("Low confidence annotations", low_confidence)
    cols[2].metric(
        "Aspects missing peer benchmark",
        sum("low_peer_support" in item.data_quality_flags for item in response.items),
    )
    cols[3].metric(
        "Aspects missing history",
        sum("insufficient_history" in item.data_quality_flags for item in response.items),
    )
    st.dataframe(
        [
            {"aspect": item.aspect, "flags": ", ".join(item.data_quality_flags)}
            for item in response.items
        ],
        use_container_width=True,
        hide_index=True,
    )


def _count_rows(items, field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        label = getattr(item, field)
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def _sentiment_rows(items) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], int] = {}
    for item in items:
        key = (item.aspect, item.sentiment)
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {"aspect": aspect, "sentiment": sentiment, "count": count}
        for (aspect, sentiment), count in sorted(grouped.items())
    ]


def _mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


if __name__ == "__main__":
    main()
