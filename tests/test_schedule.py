from datetime import date

import pandas as pd
import pytest
from factories import make_project, risk

from planpilot.engine.schedule import check_plan, cpm, deadline_days, schedule_frame
from planpilot.samples import load_sample

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


def test_deadline_days_includes_deadline():
    # Mon 2 Nov to Fri 6 Nov 2026 inclusive = 5 working days.
    assert deadline_days(make_project(DIAMOND, deadline=date(2026, 11, 6))) == 5
    # A Saturday deadline gives the same 5 days.
    assert deadline_days(make_project(DIAMOND, deadline=date(2026, 11, 7))) == 5


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
