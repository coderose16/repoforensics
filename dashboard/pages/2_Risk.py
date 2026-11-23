import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st
import altair as alt

from analysis.risk import get_risk_scores
from db.models import Session

st.set_page_config(page_title="Risk", layout="wide")
st.title("File Risk Scores")
st.caption("Score = change count (40%) + fix commits (30%) + reverts (15%) + contributors (15%).")

with Session() as session:
    results = get_risk_scores(session, repo_id=1)

if not results:
    st.warning("No data found. Run: python -m db.seed_data")
else:
    df = pd.DataFrame(results).drop(columns=["file_id"])
    df.columns = ["File", "Changes", "Fixes", "Reverts",
                  "Contributors", "Score", "Risk"]

    c1, c2, c3 = st.columns(3)
    c1.metric("HIGH risk files", int((df["Risk"] == "HIGH").sum()))
    c2.metric("MED risk files", int((df["Risk"] == "MED").sum()))
    c3.metric("LOW risk files", int((df["Risk"] == "LOW").sum()))

    label_filter = st.multiselect(
        "Show risk levels", ["HIGH", "MED", "LOW"],
        default=["HIGH", "MED", "LOW"],
    )
    shown = df[df["Risk"].isin(label_filter)]

    colors = {"HIGH": "#c0392b", "MED": "#d68910", "LOW": "#1e8449"}
    styled = shown.style.format({"Score": "{:.1f}"}).map(
        lambda v: f"color: white; background-color: {colors[v]}",
        subset=["Risk"],
    )
    st.dataframe(styled, hide_index=True)

    st.subheader("Score by file")
    chart = (
        alt.Chart(shown)
        .mark_bar()
        .encode(
            x=alt.X("File:N", sort="-y", title=None),
            y=alt.Y("Score:Q", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "Risk:N",
                scale=alt.Scale(domain=list(colors), range=list(colors.values())),
                legend=None,
            ),
            tooltip=["File", "Score", "Risk"],
        )
    )
    st.altair_chart(chart)