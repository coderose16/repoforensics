import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from analysis.fossil import find_fossils
from db.models import Session

st.set_page_config(page_title="Fossils", layout="wide")
st.title("Code Fossils")
st.caption("Functions that were deleted from the codebase, with the commit that proves it.")

with Session() as session:
    fossils = find_fossils(session, repo_id=1)

if not fossils:
    st.info("No deleted functions found. Run: python -m db.seed_data")
else:
    replaced = sum(1 for f in fossils if f["replacement"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Fossils found", len(fossils))
    c2.metric("Likely replaced", replaced)
    c3.metric("No replacement", len(fossils) - replaced)

    only_orphans = st.checkbox("Show only fossils with no replacement")

    for f in fossils:
        if only_orphans and f["replacement"]:
            continue
        title = f"{f['function']}  ·  {f['file']}  ·  deleted {f['deleted_at']:%Y-%m-%d}"
        with st.expander(title):
            st.markdown(
                f"**Deleted in commit** `{f['deleted_hash'][:8]}` "
                f"by **{f['deleted_by']}**: {f['deleted_message']}"
            )
            if f["replacement"]:
                st.success(
                    f"Likely replaced by `{f['replacement']}` "
                    f"(match score {f['score']})"
                )
            else:
                st.warning("No similar replacement found.")
            st.markdown("**Last known code**")
            st.code(f["last_code"], language="python")