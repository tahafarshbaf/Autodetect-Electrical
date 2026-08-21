"""Autodetect Electrical application entry point."""

import streamlit as st

from shared import load_css

st.set_page_config(
    page_title="Autodetect Electrical",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()

pg = st.navigation(
    [
        st.Page("views/detection.py", title="Detection", icon="🔎", default=True),
        st.Page("views/terminal.py", title="Terminal", icon="⚡"),
        st.Page("views/export.py", title="Export & Reports", icon="📄"),
    ],
    position="top",
)
pg.run()
