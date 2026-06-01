from pathlib import Path

import streamlit as st

from absa_recommender.io import load_absa_jsonl
from absa_recommender.recommender import recommend_actions

st.set_page_config(page_title="ABSA Action Recommender", layout="wide")
st.title("ABSA Action Recommender")

sample_path = Path("data/samples/absa_outputs.jsonl")
records = load_absa_jsonl(sample_path)

review_ids = [record.review_id for record in records]
selected_id = st.selectbox("Review", review_ids)
record = next(item for item in records if item.review_id == selected_id)

st.subheader("Review Text")
st.write(record.text)

st.subheader("Aspect Opinions")
st.dataframe([opinion.model_dump() for opinion in record.aspects], use_container_width=True)

st.subheader("Recommended Actions")
st.dataframe([item.model_dump() for item in recommend_actions(record)], use_container_width=True)
