"""
Entry point for the Vision Scan multi-page app.

Run this file (not the individual pages under views/):
    streamlit run app.py

Requires Streamlit >= 1.46 for the top navigation bar (position="top").
On an older Streamlit version, either upgrade:
    pip install -U streamlit
or drop the position="top" argument below to fall back to the default
sidebar navigation (which still works, just shown on the left instead of
across the top).
"""

import streamlit as st

st.set_page_config(page_title="Vision Scan", layout="wide")

pg = st.navigation(
    [
        st.Page("views/detection.py", title="Detection", icon="🔍", default=True),
        st.Page("views/terminal.py", title="Terminal", icon="🔌"),
        st.Page("views/export.py", title="Export", icon="📊"),
    ],
    position="top",
)
pg.run()
