"""Smoke tests: every page renders without an exception, with and without a project."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from planpilot.samples import load_sample
from planpilot.ui import demo_envs

ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    "app/Home.py",
    "app/pages/1_Plan.py",
    "app/pages/2_Risks.py",
    "app/pages/3_Simulation.py",
    "app/pages/4_Execution.py",
    "app/pages/5_Decide.py",
]


def run(page: str, project=None, timeout: int = 60) -> AppTest:
    at = AppTest.from_file(str(ROOT / page), default_timeout=timeout)
    if project is not None:
        at.session_state["project"] = project
    return at.run()


@pytest.fixture
def no_keys(monkeypatch):
    for var in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_with_a_demo_project(page):
    assert not run(page, load_sample("software")).exception


@pytest.mark.parametrize("page", PAGES[1:])
def test_page_without_a_project_offers_demos(page):
    at = run(page)
    assert not at.exception
    assert [b.key for b in at.button if (b.key or "").startswith("empty_")] == [
        f"empty_{env}" for env in demo_envs()
    ]


def test_demos_are_listed_in_presentation_order():
    assert demo_envs() == ["software", "event", "construction"]


def test_empty_state_button_loads_the_demo():
    at = run("app/pages/1_Plan.py")
    next(b for b in at.button if b.key == "empty_event").click()
    at.run()
    assert not at.exception
    assert at.session_state["project"].environment == "event"
    assert not [b for b in at.button if (b.key or "").startswith("empty_")]


def test_home_demo_card_loads_a_project():
    at = run("app/Home.py")
    next(b for b in at.button if b.key == "demo_construction").click()
    at.run()
    assert not at.exception
    assert at.session_state["project"].environment == "construction"


def test_without_api_keys_the_app_runs_offline(no_keys):
    at = run("app/Home.py")
    assert not at.exception
    assert next(b for b in at.button if b.label == "Generate plan").disabled
    assert at.toggle[0].disabled
    assert any("No API key" in c.value for c in at.sidebar.caption)
    # LLM buttons on other pages are disabled too
    risks = run("app/pages/2_Risks.py", load_sample("software"))
    assert next(b for b in risks.button if "risks with the LLM" in b.label).disabled
