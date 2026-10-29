"""Shared Streamlit sidebar and project state."""

import streamlit as st

from planpilot.config import DEFAULT_SEED, PRESETS
from planpilot.models import Project
from planpilot.samples import available_samples, load_sample


def sidebar() -> Project | None:
    """Render the sidebar and return the current project (or None)."""
    with st.sidebar:
        st.number_input("Seed", min_value=0, value=DEFAULT_SEED, step=1, key="seed")
        samples = available_samples()
        env = st.selectbox(
            "Demo project", samples, format_func=lambda e: PRESETS[e].label, key="demo_env"
        )
        if st.button("Load demo project", width="stretch"):
            st.session_state["project"] = load_sample(env)
    return st.session_state.get("project")
