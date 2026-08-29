"""Deprecated. The product UI is the unified AI-CIO app."""
import streamlit as st

st.set_page_config(page_title="Moved to AI-CIO", layout="centered")
st.title("This screen is no longer the product")
st.write(
    "Psychometrics, finances, goals, and CAS now live in one AI-CIO journey. "
    "From the repository root run:"
)
st.code("python -m ai_cio.api\nstreamlit run frontend/app.py")
