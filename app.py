"""Autodetect Electrical application entry point."""

import streamlit as st

st.set_page_config(
    page_title="Autodetect Electrical",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Config (model path, PR file path, etc.) is validated the moment config.py
# is imported - which happens as soon as shared.py is imported below. If
# that raises, the ConfigError class itself may never finish importing
# (the failure happens mid-import), so we catch broadly here rather than
# naming the exception type, and show its message as a clear, styled
# error instead of a raw traceback.
try:
    from shared import load_css
except Exception as e:
    st.error(f"⚠️ Configuration error\n\n{e}")
    st.stop()

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