import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd
from db.models import Session, Repository
from analysis.ownership import get_ownership

st.title("File Ownership")
st.caption("Who started each file, and who maintains it now (last 5 changes).")

with Session() as s:
    repo = s.query(Repository).order_by(Repository.repo_id.desc()).first()
    if repo is None:
        st.info("No data yet. Run analyze.py first.")
        st.stop()
    rows = get_ownership(s, repo.repo_id)

if not rows:
    st.info("No ownership data found.")
    st.stop()

df = pd.DataFrame(rows).rename(columns={
    "file": "File", "original_author": "Original author",
    "top_recent_author": "Top recent author",
    "contributors": "Contributors", "drift": "Ownership drift"})

c1, c2 = st.columns(2)
c1.metric("Files", len(df))
c2.metric("Files with ownership drift", int(df["Ownership drift"].sum()))
st.dataframe(df, hide_index=True)