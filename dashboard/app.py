import sys
from pathlib import Path

# let this file find the db/ folder one level up
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from db.models import Commit, Developer, Session

st.set_page_config(page_title="RepoForensics", layout="wide")
st.title("RepoForensics")
st.caption("Mining a Git repository's history for risky files and code fossils.")

with Session() as session:
    rows = (
        session.query(
            Commit.hash,
            Developer.name,
            Commit.message,
            Commit.committed_at,
            Commit.is_fix,
            Commit.is_revert,
        )
        .join(Developer, Commit.developer_id == Developer.developer_id)
        .order_by(Commit.committed_at.desc())
        .all()
    )

if not rows:
    st.warning("No commits found. Run: python -m db.seed_data")
else:
    df = pd.DataFrame(
        rows,
        columns=["Hash", "Author", "Message", "Date", "Fix", "Revert"],
    )
    df["Hash"] = df["Hash"].str[:8]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total commits", len(df))
    c2.metric("Fix commits", int(df["Fix"].sum()))
    c3.metric("Revert commits", int(df["Revert"].sum()))

    st.subheader("Commits")
    st.dataframe(df, hide_index=True)