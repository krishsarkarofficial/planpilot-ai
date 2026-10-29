from test_llm import FakeTransport

from planpilot.llm.chains import status_chain
from planpilot.llm.client import LLMClient
from planpilot.samples import load_progress, load_sample
from planpilot.status import StatusReport, status_facts, template_status, unknown_figures

PROJECT = load_sample("event")
PROGRESS = load_progress("event")
FACTS = status_facts(PROJECT, PROGRESS)
TEMPLATE = template_status(PROJECT, PROGRESS)


def test_facts_hold_the_computed_indices():
    assert "SPI: 0.82" in FACTS and "CPI: 0.90" in FACTS
    assert "Overall status (RAG): RED" in FACTS


def test_template_report_uses_only_facts():
    assert TEMPLATE.headline.startswith("RED")
    assert unknown_figures(TEMPLATE, FACTS) == []


def test_invented_and_rounded_figures():
    report = TEMPLATE.model_copy(
        update={"summary": "SPI rounds to 0.8, but 18% of the work is missing over 12,345 days."}
    )
    assert unknown_figures(report, FACTS) == ["18", "12345"]  # 0.8 is a rounded 0.82


def test_status_chain_retries_an_invented_figure_and_unknown_id(tmp_path):
    invented = TEMPLATE.model_copy(update={"cost": "The project will overrun by 71.3 percent."})
    bad_id = TEMPLATE.model_copy(update={"issues": ["T77 is late."]})
    t = FakeTransport(
        invented.model_dump_json(), bad_id.model_dump_json(), TEMPLATE.model_dump_json()
    )
    report = status_chain(
        LLMClient(transport=t, cache_dir=tmp_path, offline=False), PROJECT, PROGRESS
    )
    assert isinstance(report, StatusReport) and report == TEMPLATE
    assert len(t.calls) == 3
    assert "figure 71.3 is not in the facts" in t.calls[1][1]
    assert "unknown task or risk ids: T77" in t.calls[2][1]
    assert "SPI: 0.82" in t.calls[0][1]  # the prompt carries the precomputed facts
