import pytest

from planpilot.engine.montecarlo import simulate
from planpilot.samples import available_samples, load_sample


@pytest.mark.parametrize("env", available_samples())
def test_sample_deadline_is_calibrated(env):
    # make_demo_data.py sets the deadline near baseline P65, so the decision module has room.
    assert 0.6 <= simulate(load_sample(env)).prob_on_time <= 0.8
