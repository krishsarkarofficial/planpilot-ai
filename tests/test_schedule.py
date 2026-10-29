from datetime import date

import pandas as pd
import pytest

from planpilot.engine.schedule import check_plan, cpm, schedule_frame
from planpilot.models import Project, Risk
from planpilot.samples import load_sample


def make_project(tasks: list[tuple], deadline=date(2026, 12, 31), risks=()) -> Project:
    """tasks: (id, phase, most_likely, depends_on)."""
    return Project(
        name="test",
        environment="software",
        brief="",
        start_date=date(2026, 11, 2),  # Monday
        deadline=deadline,
        team={"developer": 1},
        tasks=[
            {
                "id": tid,
                "name": tid,
                "phase": phase,
                "role": "developer",
                "optimistic": m,
                "most_likely": m,
                "pessimistic": m + 1,
                "depends_on": deps,
            }
            for tid, phase, m, deps in tasks
        ],
        risks=list(risks),
    )


def risk(rid: str, category: str) -> Risk:
    return Risk(
        id=rid,
        title=rid,
        category=category,
        cause="c",
        event="e",
        effect="f",
        probability=0.5,
        impact_days=1,
        affected_task_ids=["T01"],
        owner_role="developer",
        response_strategy="accept",
        response="r",
    )


DIAMOND = [
    ("T01", "A", 3, []),
    ("T02", "A", 2, ["T01"]),
    ("T03", "B", 4, ["T01"]),
    ("T04", "B", 1, ["T02", "T03"]),
]


def test_cpm_known_network():
    s = cpm(make_project(DIAMOND))
    assert s.duration == 8
    assert s.critical == ["T01", "T03", "T04"]
    assert s.slack["T02"] == 2
    assert s.es["T04"] == 7 and s.lf["T02"] == 7


def test_cpm_with_given_durations():
    s = cpm(make_project(DIAMOND), {"T01": 3, "T02": 6, "T03": 4, "T04": 1})
    assert s.duration == 10
    assert s.critical == ["T01", "T02", "T04"]


def test_dates_skip_weekends():
    df = schedule_frame(make_project(DIAMOND), cpm(make_project(DIAMOND)))
    row = df.set_index("id")
    # T01 occupies working days 0-2: Mon 2 Nov to Wed 4 Nov.
    assert row.loc["T01", "start"] == pd.Timestamp("2026-11-02")
    assert row.loc["T01", "finish"] == pd.Timestamp("2026-11-04")
    # T03 occupies days 3-6: Thu 5 Nov to Tue 10 Nov (skips the weekend).
    assert row.loc["T03", "start"] == pd.Timestamp("2026-11-05")
    assert row.loc["T03", "finish"] == pd.Timestamp("2026-11-10")


def test_frozen_project_passes_checks():
    errors, warnings = check_plan(load_sample("software"))
    assert errors == []
    assert len(warnings) == 1 and "only one start task" in warnings[0]


def test_too_few_tasks_and_small_phase_are_errors():
    errors, _ = check_plan(make_project(DIAMOND + [("T05", "C", 1, ["T04"])]))
    assert any("expected 12-30" in e for e in errors)
    assert any("phase 'C'" in e for e in errors)


def test_dangling_task_warning():
    tasks = DIAMOND + [("T05", "B", 1, ["T01"])]  # T05 has no successor and ends early
    _, warnings = check_plan(make_project(tasks))
    assert any("no successor" in w and "T05" in w for w in warnings)


def test_no_parallel_paths_warning():
    chain = [("T01", "A", 2, []), ("T02", "A", 2, ["T01"]), ("T03", "A", 2, ["T02"])]
    _, warnings = check_plan(make_project(chain))
    assert any("no parallel paths" in w for w in warnings)
    _, warnings = check_plan(make_project(DIAMOND))
    assert not any("no parallel paths" in w for w in warnings)


@pytest.mark.parametrize("deadline", [date(2026, 11, 4), date(2027, 6, 1)])
def test_timeframe_warning(deadline):
    _, warnings = check_plan(make_project(DIAMOND, deadline=deadline))
    assert any("stated timeframe" in w for w in warnings)


def test_risk_category_warning():
    _, warnings = check_plan(make_project(DIAMOND, risks=[risk("R01", "technical")]))
    assert any("categories" in w for w in warnings)
    three = [risk("R01", "technical"), risk("R02", "scope"), risk("R03", "external")]
    _, warnings = check_plan(make_project(DIAMOND, risks=three))
    assert not any("categories" in w for w in warnings)
