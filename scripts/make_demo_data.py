"""Validate the frozen demo projects, calibrate each deadline to about the baseline P65 and
write each project's weekly progress CSV.

Run: python scripts/make_demo_data.py
"""

import json
import re

from planpilot.config import DEFAULT_SEED, PROGRESS_DEFAULTS
from planpilot.engine.evm import default_as_of_week, simulate_progress, status_at
from planpilot.engine.montecarlo import simulate
from planpilot.engine.schedule import check_plan, finish_date
from planpilot.models import Project
from planpilot.samples import SAMPLE_DIR, available_samples, progress_path

CALIBRATION_PERCENTILE = 65
DEADLINE_FIELD = re.compile(r'"deadline":\s*"\d{4}-\d{2}-\d{2}"')


def calibrate(env: str) -> Project:
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

    calibrated = Project.model_validate(json.loads(new_text))
    res = simulate(calibrated, seed=DEFAULT_SEED)
    print(
        f"{env}: deadline {deadline} ({res.deadline_days} working days), "
        f"P(on time) {res.prob_on_time:.2f}, warnings: {len(warnings)}"
    )
    return calibrated


def write_progress(env: str, project: Project) -> None:
    week = default_as_of_week(project)
    progress = simulate_progress(project, week, seed=DEFAULT_SEED, **PROGRESS_DEFAULTS[env])
    progress.to_csv(progress_path(env), index=False, encoding="utf-8", lineterminator="\n")
    s = status_at(project, progress)
    print(f"  progress to week {week}: SPI {s.spi:.2f}, CPI {s.cpi:.2f}, {s.rag}")


if __name__ == "__main__":
    for env in available_samples():
        write_progress(env, calibrate(env))
