"""Critical path method on most-likely durations, calendar dates and plan checks."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from planpilot.models import Project, topological_order

EPS = 1e-9
MIN_TASKS, MAX_TASKS = 12, 30
MIN_RISK_CATEGORIES = 3


@dataclass
class Schedule:
    order: list[str]
    es: dict[str, float]
    ef: dict[str, float]
    ls: dict[str, float]
    lf: dict[str, float]
    slack: dict[str, float]
    duration: float
    critical: list[str]  # topological order


def successors(project: Project) -> dict[str, list[str]]:
    succ: dict[str, list[str]] = {t.id: [] for t in project.tasks}
    for t in project.tasks:
        for d in t.depends_on:
            succ[d].append(t.id)
    return succ


def cpm(project: Project, durations: dict[str, float] | None = None) -> Schedule:
    """Forward and backward pass. Uses most-likely durations unless `durations` is given."""
    tasks = {t.id: t for t in project.tasks}
    dur = durations or {tid: t.most_likely for tid, t in tasks.items()}
    order = topological_order(project.tasks)
    succ = successors(project)

    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    for tid in order:
        es[tid] = max((ef[d] for d in tasks[tid].depends_on), default=0.0)
        ef[tid] = es[tid] + dur[tid]
    duration = max(ef.values())

    ls: dict[str, float] = {}
    lf: dict[str, float] = {}
    for tid in reversed(order):
        lf[tid] = min((ls[s] for s in succ[tid]), default=duration)
        ls[tid] = lf[tid] - dur[tid]

    slack = {tid: ls[tid] - es[tid] for tid in order}
    critical = [tid for tid in order if slack[tid] <= EPS]
    return Schedule(order, es, ef, ls, lf, slack, duration, critical)


def working_day_to_date(start, offsets) -> np.ndarray:
    """Calendar date of working-day offset(s) from `start` (Mon-Fri calendar)."""
    return np.busday_offset(np.datetime64(start, "D"), offsets, roll="forward")


def schedule_frame(project: Project, sched: Schedule) -> pd.DataFrame:
    """One row per task in topological order, with dates.

    A task occupies working days [ES, EF). `start` is the first working day and
    `finish` the last working day it occupies (inclusive).
    """
    tasks = {t.id: t for t in project.tasks}
    es = np.array([sched.es[t] for t in sched.order])
    ef = np.array([sched.ef[t] for t in sched.order])
    start_idx = np.floor(es + EPS).astype(int)
    finish_idx = np.maximum(np.ceil(ef - EPS).astype(int) - 1, start_idx)
    return pd.DataFrame(
        {
            "id": sched.order,
            "name": [tasks[t].name for t in sched.order],
            "phase": [tasks[t].phase for t in sched.order],
            "role": [tasks[t].role for t in sched.order],
            "o": [tasks[t].optimistic for t in sched.order],
            "m": [tasks[t].most_likely for t in sched.order],
            "p": [tasks[t].pessimistic for t in sched.order],
            "depends_on": [", ".join(tasks[t].depends_on) for t in sched.order],
            "es": es,
            "ef": ef,
            "slack": [sched.slack[t] for t in sched.order],
            "critical": [sched.slack[t] <= EPS for t in sched.order],
            "start": pd.to_datetime(working_day_to_date(project.start_date, start_idx)),
            "finish": pd.to_datetime(working_day_to_date(project.start_date, finish_idx)),
        }
    )


def stated_timeframe_days(project: Project) -> int:
    """Working days from start_date to deadline."""
    return int(np.busday_count(project.start_date, project.deadline))


def check_plan(project: Project) -> tuple[list[str], list[str]]:
    """Semantic checks on a structurally valid project. Returns (errors, warnings).

    Structural errors (cycles, unknown ids or roles) are already rejected by
    Project validation.
    """
    errors: list[str] = []
    warnings: list[str] = []

    n = len(project.tasks)
    if not MIN_TASKS <= n <= MAX_TASKS:
        errors.append(f"plan has {n} tasks; expected {MIN_TASKS}-{MAX_TASKS}")
    phase_sizes: dict[str, int] = {}
    for t in project.tasks:
        phase_sizes[t.phase] = phase_sizes.get(t.phase, 0) + 1
    for phase, size in phase_sizes.items():
        if size < 2:
            errors.append(f"phase '{phase}' has only {size} task; expected at least 2")

    sched = cpm(project)
    succ = successors(project)
    sinks = [tid for tid in sched.order if not succ[tid]]
    dangling = [tid for tid in sinks if sched.ef[tid] < sched.duration - EPS]
    if dangling:
        warnings.append(
            f"tasks with no successor that do not finish the project: {', '.join(dangling)}"
        )

    starts = [t.id for t in project.tasks if not t.depends_on]
    if len(starts) == 1:
        warnings.append(f"only one start task ({starts[0]}); work cannot begin in parallel")

    if not _has_overlap(sched):
        warnings.append("no parallel paths: no two tasks overlap in the schedule")

    timeframe = stated_timeframe_days(project)
    if not 0.5 * timeframe <= sched.duration <= 2 * timeframe:
        warnings.append(
            f"CPM duration {sched.duration:g} working days is outside 0.5x-2x of the "
            f"stated timeframe ({timeframe} working days)"
        )

    categories = {r.category for r in project.risks}
    if len(categories) < MIN_RISK_CATEGORIES:
        warnings.append(
            f"risk register covers {len(categories)} categories; "
            f"expected at least {MIN_RISK_CATEGORIES}"
        )

    return errors, warnings


def _has_overlap(sched: Schedule) -> bool:
    intervals = sorted((sched.es[t], sched.ef[t]) for t in sched.order if sched.ef[t] > sched.es[t])
    latest_end = -1.0
    for start, end in intervals:
        if start < latest_end - EPS:
            return True
        latest_end = max(latest_end, end)
    return False
