"""Shared Streamlit sidebar, project state and cached simulation."""

import streamlit as st
from pydantic import TypeAdapter

from planpilot.config import DEFAULT_SEED, PRESETS, PROVIDERS, llm_available, offline_default
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
    """Offline when the user switched it on or when no provider has an API key."""
    return not llm_available() or bool(st.session_state.get("offline", offline_default()))


REPO_URL = "https://github.com/krishsarkarofficial/planpilot-ai"

_CSS = """
<style>
.block-container { padding-top: 2.5rem; max-width: 1200px; }
[data-testid="stMetricValue"] { font-size: 1.6rem; }
[data-testid="stMetricValue"] > div { white-space: normal; overflow: visible; text-overflow: clip; }
footer { visibility: hidden; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def load_demo(env: str) -> None:
    st.session_state["project"] = load_sample(env)
    st.session_state["demo_env"] = env
    st.session_state.pop("generation", None)


def demo_envs() -> list[str]:
    """Demo environments in presentation order (software, event, construction)."""
    order = list(PRESETS)
    return sorted(available_samples(), key=lambda e: order.index(e) if e in order else len(order))


def require_project(project: Project | None) -> Project:
    """Return the project, or show a friendly empty state with one-click demos and stop."""
    if project is not None:
        return project
    st.info("No project is loaded yet. Open a demo project to explore this page.")
    envs = demo_envs()
    for col, env in zip(st.columns(len(envs)), envs, strict=True):
        label = PRESETS[env].label.partition(" (")[0]
        if col.button(f"{label} demo", key=f"empty_{env}", width="stretch"):
            load_demo(env)
            st.rerun()
    st.stop()


def sidebar() -> Project | None:
    """Render the sidebar and return the current project (or None)."""
    inject_css()
    with st.sidebar:
        k = _persistent_widget("offline", offline_default())
        st.toggle(
            "Offline (frozen demo projects only)",
            key=k,
            on_change=_persist,
            args=(k, "offline"),
            disabled=not llm_available(),
        )
        if not llm_available():
            st.caption("No API key is configured, so this copy runs offline on the demo projects.")
        elif is_offline():
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
            load_demo(env)
        st.divider()
        st.caption(
            "Demo data is synthetic. PlanPilot AI supports decisions; it does not replace a "
            f"project manager. [Source code]({REPO_URL})"
        )
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
