from pathlib import Path

import streamlit as st

from absa_recommender.config import load_label_schema
from absa_recommender.normalize_absa import flatten_reviews, load_absa_jsonl

st.set_page_config(page_title="ABSA Action Recommender", layout="wide")
st.title("ABSA Action Recommender")

sample_path = Path("data/samples/absa_outputs.jsonl")
records = load_absa_jsonl(sample_path)
label_schema = load_label_schema("configs/label_schema.yaml")

review_ids = [record.review_id for record in records]
selected_id = st.selectbox("Review", review_ids)
record = next(item for item in records if item.review_id == selected_id)

st.subheader("Review Text")
st.write(record.review_text)

st.subheader("ABSA Annotations")
st.dataframe([annotation.model_dump() for annotation in record.annotations], use_container_width=True)

st.subheader("Flattened Extractions")
st.dataframe(
    [item.model_dump() for item in flatten_reviews([record], label_schema)],
    use_container_width=True,
)
