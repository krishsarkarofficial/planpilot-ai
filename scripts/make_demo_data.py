"""Validate the frozen demo projects and calibrate each deadline to about the baseline P65.

Run: python scripts/make_demo_data.py
"""

import json
import re

from planpilot.config import DEFAULT_SEED
from planpilot.engine.montecarlo import simulate
from planpilot.engine.schedule import check_plan, finish_date
from planpilot.models import Project
from planpilot.samples import SAMPLE_DIR, available_samples

CALIBRATION_PERCENTILE = 65
DEADLINE_FIELD = re.compile(r'"deadline":\s*"\d{4}-\d{2}-\d{2}"')


def calibrate(env: str) -> None:
    path = SAMPLE_DIR / f"{env}.json"
    text = path.read_text(encoding="utf-8")
    project = Project.model_validate(json.loads(text))
    errors, warnings = check_plan(project)
    if errors:
        raise SystemExit(f"{env}: plan check errors: {errors}")

    res = simulate(project, seed=DEFAULT_SEED)
    deadline = finish_date(project, res.percentile(CALIBRATION_PERCENTILE))
    new_text, count = DEADLINE_FIELD.subn(f'"deadline": "{deadline.isoformat()}"', text)
    if count != 1:
        raise SystemExit(f"{env}: expected one deadline field, found {count}")
    path.write_text(new_text, encoding="utf-8")

    calibrated = simulate(Project.model_validate(json.loads(new_text)), seed=DEFAULT_SEED)
    print(
        f"{env}: deadline {deadline} ({calibrated.deadline_days} working days), "
        f"P(on time) {calibrated.prob_on_time:.2f}, warnings: {len(warnings)}"
    )


if __name__ == "__main__":
    for env in available_samples():
        calibrate(env)
