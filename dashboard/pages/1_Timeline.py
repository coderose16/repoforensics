import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd
from db.models import Session, Function, FunctionChange, Commit, Developer, File

st.title("Function Timeline")

with Session() as s:
    funcs = s.query(Function, File).join(File, File.file_id == Function.file_id).all()
    labels = {f"{fi.path} :: {fn.name} (#{fn.function_id})": fn.function_id
              for fn, fi in funcs}
    if not labels:
        st.info("No functions yet. Run the tracker first.")
        st.stop()

    choice = st.selectbox("Pick a function", list(labels))
    rows = (s.query(FunctionChange, Commit, Developer)
            .join(Commit, Commit.commit_id == FunctionChange.commit_id)
            .join(Developer, Developer.developer_id == Commit.developer_id)
            .filter(FunctionChange.function_id == labels[choice])
            .order_by(Commit.committed_at, Commit.commit_id.desc())
            .all())

    st.table(pd.DataFrame([{
        "Event": ch.change_type,
        "Commit": c.hash[:7],
        "Author": d.name,
        "Date": c.committed_at,
        "Message": c.message,
    } for ch, c, d in rows]))