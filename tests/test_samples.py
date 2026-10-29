import pandas as pd
import pytest

from planpilot.config import PROGRESS_DEFAULTS
from planpilot.engine.evm import default_as_of_week, simulate_progress, status_at
from planpilot.engine.montecarlo import simulate
from planpilot.engine.schedule import check_plan
from planpilot.samples import available_samples, load_progress, load_sample


def test_all_three_environments_have_a_demo_project():
    assert available_samples() == ["construction", "event", "software"]


@pytest.mark.parametrize("env", available_samples())
def test_sample_passes_plan_checks(env):
    project = load_sample(env)
    errors, _ = check_plan(project)
    assert errors == []
    assert len({r.category for r in project.risks}) >= 4


@pytest.mark.parametrize("env", available_samples())
def test_sample_deadline_is_calibrated(env):
    # make_demo_data.py sets the deadline near baseline P65, so the decision module has room.
    assert 0.6 <= simulate(load_sample(env)).prob_on_time <= 0.8


@pytest.mark.parametrize("env", available_samples())
def test_progress_csv_matches_the_generator(env):
    # A stale CSV (plan or defaults changed without re-running make_demo_data.py) fails here.
    project = load_sample(env)
    expected = simulate_progress(project, default_as_of_week(project), **PROGRESS_DEFAULTS[env])
    pd.testing.assert_frame_equal(load_progress(env), expected, check_dtype=False)
    s = status_at(project, expected)
    assert s.spi == pytest.approx(0.82, abs=0.02) and s.cpi == pytest.approx(0.90, abs=0.02)
