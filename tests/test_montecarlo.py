from datetime import date

import numpy as np
import pytest
from factories import make_project, risk

from planpilot.engine.montecarlo import simulate, triangular_from_uniform
from planpilot.engine.schedule import cpm

DIAMOND = [
    ("T01", "A", (2, 3, 5), []),
    ("T02", "A", (1, 2, 4), ["T01"]),
    ("T03", "B", (3, 4, 8), ["T01"]),
    ("T04", "B", (1, 1, 2), ["T02", "T03"]),
]
FIXED = [(tid, ph, (m, m, m), deps) for tid, ph, (_, m, _), deps in DIAMOND]  # o = m = p


def test_single_task_mean_is_triangular_mean():
    res = simulate(make_project([("T01", "A", (2, 4, 9), [])]), seed=1)
    assert res.durations.mean() == pytest.approx((2 + 4 + 9) / 3, abs=0.05)
    assert 2 <= res.durations.min() and res.durations.max() <= 9


def test_triangular_handles_degenerate_bounds():
    u = np.array([0.0, 0.3, 1.0])
    assert np.all(triangular_from_uniform(u, 3, 3, 3) == 3)
    assert np.all(np.diff(triangular_from_uniform(u, 2, 2, 6)) >= 0)  # m == o
    assert np.all(np.diff(triangular_from_uniform(u, 2, 6, 6)) >= 0)  # m == p


def test_deterministic_with_seed():
    p = make_project(DIAMOND, risks=[risk("R01", tasks=("T03",))])
    a, b = simulate(p, seed=7), simulate(p, seed=7)
    assert np.array_equal(a.durations, b.durations) and np.array_equal(a.costs, b.costs)
    assert not np.array_equal(a.durations, simulate(p, seed=8).durations)


def test_percentiles_ordered():
    res = simulate(make_project(DIAMOND, risks=[risk("R01", tasks=("T03",))]))
    for of in ("duration", "cost"):
        assert res.percentile(50, of) <= res.percentile(80, of) <= res.percentile(90, of)


def test_fixed_durations_no_risk_equal_cpm():
    p = make_project(FIXED, risks=[risk("R01", probability=0.0, impact=5)])
    res = simulate(p, n=500)
    assert np.all(res.durations == cpm(p).duration)  # 8 working days


def test_deadline_boundary():
    # CPM duration is 8 working days: Mon 2 Nov .. Wed 11 Nov 2026.
    assert simulate(make_project(FIXED, deadline=date(2026, 11, 11)), n=100).prob_on_time == 1.0
    assert simulate(make_project(FIXED, deadline=date(2026, 11, 10)), n=100).prob_on_time == 0.0


def test_certain_risk_adds_impact():
    p = make_project(FIXED, risks=[risk("R01", probability=1.0, impact=2, tasks=("T03",))])
    assert np.all(simulate(p, n=100).durations == 10)


def test_criticality_and_tornado():
    res = simulate(make_project(FIXED), n=100)
    assert res.criticality == {"T01": 1.0, "T02": 0.0, "T03": 1.0, "T04": 1.0}
    assert all(v == 0.0 for v in res.tornado.values())  # constant durations give no NaN

    res = simulate(make_project(DIAMOND))
    assert next(iter(res.tornado)) == "T03"  # widest task on the main path dominates
    assert res.criticality["T03"] > res.criticality["T02"]


def test_cost_uses_role_rates_and_fixed_cost():
    p = make_project(FIXED)
    base = simulate(p, n=10)
    assert np.all(base.costs == 10 * 4000)  # 10 task-days x developer rate
    assert np.all(simulate(p, n=10, fixed_cost=500).costs == base.costs + 500)
    assert np.all(simulate(p, n=10, rates={"developer": 1000}).costs == 10 * 1000)


def test_common_random_numbers_survive_cutting_a_task():
    full = make_project(DIAMOND + [("T05", "B", (1, 2, 3), ["T01"])])
    cut = make_project(DIAMOND)
    a, b = simulate(full, seed=3), simulate(cut, seed=3)
    for tid in b.task_ids:
        assert np.array_equal(
            a.task_durations[:, a.task_ids.index(tid)], b.task_durations[:, b.task_ids.index(tid)]
        )


def test_lower_risk_probability_only_removes_events():
    hi = make_project(DIAMOND, risks=[risk("R01", probability=0.6, impact=3, tasks=("T03",))])
    lo = make_project(DIAMOND, risks=[risk("R01", probability=0.3, impact=3, tasks=("T03",))])
    a, b = simulate(hi), simulate(lo)
    assert np.all(b.durations <= a.durations)
    # Every percentile drops. (The P90-P50 spread need not: at p=0.6 the delay shifts P50 too.)
    for q in (50, 80, 90):
        assert b.percentile(q) <= a.percentile(q)
