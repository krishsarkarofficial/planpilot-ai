"""Shared Streamlit sidebar, project state and cached simulation."""

import streamlit as st
from pydantic import TypeAdapter

from planpilot.config import DEFAULT_SEED, PRESETS, PROVIDERS, offline_default
from planpilot.engine.decision import Comparison, compare
from planpilot.engine.montecarlo import SimResult, simulate
from planpilot.llm.client import LLMClient
from planpilot.models import Option, Project
from planpilot.samples import available_samples, load_sample


def _persist(widget_key: str, store_key: str) -> None:
    st.session_state[store_key] = st.session_state[widget_key]


def _persistent_widget(store_key: str, default) -> str:
    """Streamlit drops widget state on page switch, so keep the value under a plain key."""
    st.session_state.setdefault(store_key, default)
    widget_key = f"_{store_key}"
    st.session_state[widget_key] = st.session_state[store_key]
    return widget_key


@st.cache_resource
def _client() -> LLMClient:
    """One client per server process, so a switch to the fallback provider sticks."""
    return LLMClient()


def llm_client() -> LLMClient:
    client = _client()
    client.offline = is_offline()
    return client


def is_offline() -> bool:
    return bool(st.session_state.get("offline", offline_default()))


def sidebar() -> Project | None:
    """Render the sidebar and return the current project (or None)."""
    with st.sidebar:
        k = _persistent_widget("offline", offline_default())
        st.toggle(
            "Offline (frozen demo projects only)",
            key=k,
            on_change=_persist,
            args=(k, "offline"),
        )
        if is_offline():
            st.caption("LLM: off")
        else:
            provider = _client().provider
            st.caption(f"LLM: {provider} · `{PROVIDERS[provider]['model']}`")
        k = _persistent_widget("seed", DEFAULT_SEED)
        st.number_input("Seed", min_value=0, step=1, key=k, on_change=_persist, args=(k, "seed"))
        samples = available_samples()
        k = _persistent_widget("demo_env", "software" if "software" in samples else samples[0])
        env = st.selectbox(
            "Demo project",
            samples,
            format_func=lambda e: PRESETS[e].label,
            key=k,
            on_change=_persist,
            args=(k, "demo_env"),
        )
        if st.button("Load demo project", width="stretch"):
            st.session_state["project"] = load_sample(env)
            st.session_state.pop("generation", None)
    return st.session_state.get("project")


def current_seed() -> int:
    return int(st.session_state.get("seed", DEFAULT_SEED))


@st.cache_data(show_spinner="Running 10,000 simulations…", max_entries=32)
def _simulate_cached(project_json: str, seed: int) -> SimResult:
    return simulate(Project.model_validate_json(project_json), seed=seed)


def run_simulation(project: Project, seed: int) -> SimResult:
    """Monte Carlo result, cached on the project's JSON and the seed."""
    return _simulate_cached(project.model_dump_json(), seed)


_OPTIONS = TypeAdapter(list[Option])


@st.cache_data(show_spinner="Simulating each option…", max_entries=8)
def _compare_cached(project_json: str, options_json: str, seed: int) -> Comparison:
    return compare(
        Project.model_validate_json(project_json), _OPTIONS.validate_json(options_json), seed=seed
    )


def run_comparison(project: Project, options: list[Option], seed: int) -> Comparison:
    """Baseline and options simulated with one seed, cached on the project, options and seed."""
    return _compare_cached(project.model_dump_json(), _OPTIONS.dump_json(options).decode(), seed)
