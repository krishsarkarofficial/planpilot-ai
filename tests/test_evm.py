import pandas as pd
import pytest
from factories import make_project

from planpilot.engine.evm import (
    budgets,
    evm_series,
    planned_pct,
    rag,
    simulate_progress,
    status_at,
    task_progress,
)

CHAIN = [("T01", "A", 5, []), ("T02", "A", 10, ["T01"])]


def progress(rows):
    return pd.DataFrame(rows, columns=["week", "task_id", "actual_pct", "actual_cost"])


def test_hand_calculated_indices():
    # Two 5-day developer tasks at 4000/day: budgets 20000 each, BAC 40000.
    # Week 1 plan: T01 done (PV 20000). Actual: T01 80% done (EV 16000), spent 18000.
    project = make_project([("T01", "A", 5, []), ("T02", "A", 5, ["T01"])])
    prog = progress([(1, "T01", 0.8, 18000), (1, "T02", 0.0, 0.0)])
    s = status_at(project, prog)
    assert s.bac == 40000
    assert (s.pv, s.ev, s.ac) == (20000, 16000, 18000)
    assert s.spi == pytest.approx(0.8)
    assert s.cpi == pytest.approx(16000 / 18000)
    assert s.eac == pytest.approx(45000)
    assert s.vac == pytest.approx(-5000)
    assert s.rag == "red"


def test_planned_pct_is_linear_between_es_and_ef():
    project = make_project(CHAIN)  # T01 [0, 5), T02 [5, 15)
    assert planned_pct(project, 0) == {"T01": 0.0, "T02": 0.0}
    assert planned_pct(project, 1) == {"T01": 1.0, "T02": 0.0}  # T02 not started before ES
    assert planned_pct(project, 2)["T02"] == pytest.approx(0.5)
    assert planned_pct(project, 3)["T02"] == 1.0  # done after EF
    assert planned_pct(project, 10)["T02"] == 1.0


@pytest.mark.parametrize(
    ("spi", "cpi", "expected"),
    [
        (1.0, 1.0, "green"),
        (0.95, 0.99, "green"),
        (0.949, 1.0, "amber"),
        (1.0, 0.85, "amber"),
        (0.849, 1.0, "red"),
        (0.95, 0.80, "red"),
    ],
)
def test_rag_thresholds(spi, cpi, expected):
    assert rag(spi, cpi) == expected


def test_simulate_progress_is_deterministic_and_keyed_to_the_plan():
    project = make_project(CHAIN + [("T03", "B", 4, []), ("T04", "B", 6, ["T03"])])
    a = simulate_progress(project, 3, slip=1.3, cost_overrun=1.1, seed=7)
    b = simulate_progress(project, 3, slip=1.3, cost_overrun=1.1, seed=7)
    pd.testing.assert_frame_equal(a, b)
    assert set(a["task_id"]) == {t.id for t in project.tasks}
    assert sorted(a["week"].unique()) == [1, 2, 3]
    assert not a.equals(simulate_progress(project, 3, slip=1.3, cost_overrun=1.1, seed=8))


def test_progress_is_cumulative_and_bounded():
    project = make_project(CHAIN)
    prog = simulate_progress(project, 6, slip=1.4)
    assert prog["actual_pct"].between(0, 1).all()
    for _, g in prog.groupby("task_id"):
        assert g["actual_pct"].is_monotonic_increasing
        assert g["actual_cost"].is_monotonic_increasing


def test_slip_and_overrun_move_the_indices():
    project = make_project(CHAIN + [("T03", "B", 4, []), ("T04", "B", 6, ["T03"])])
    on_plan = status_at(project, simulate_progress(project, 2))
    late = status_at(project, simulate_progress(project, 2, slip=1.3, cost_overrun=1.2))
    assert late.spi < on_plan.spi
    assert late.cpi == pytest.approx(1 / 1.2, rel=0.06)  # cost noise is +-5%
    assert late.eac > late.bac


def test_zero_planned_value_gives_nan_not_an_error():
    project = make_project(CHAIN)
    series = evm_series(project, progress([(0, "T01", 0.0, 0.0), (0, "T02", 0.0, 0.0)]))
    assert series["spi"].isna().all() and series["cpi"].isna().all()


def test_task_progress_lists_the_worst_schedule_variance_first():
    project = make_project(CHAIN + [("T03", "B", 4, []), ("T04", "B", 6, ["T03"])])
    prog = progress(
        [(1, "T01", 1.0, 20000), (1, "T02", 0.0, 0), (1, "T03", 0.25, 5000), (1, "T04", 0.0, 0)]
    )
    df = task_progress(project, prog)
    assert df.iloc[0]["id"] == "T03"  # planned 100% at week 1, actual 25%
    b = budgets(project)
    assert df.set_index("id").loc["T03", "sv"] == pytest.approx(-0.75 * b["T03"])
