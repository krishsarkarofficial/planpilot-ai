"""Earned value management on the CPM plan, and a synthetic progress generator.

Budget per task = most-likely duration x role rate (no risk allowance), so BAC is the
most-likely plan cost, not the Monte Carlo forecast.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from planpilot.config import AS_OF_SHARE, DEFAULT_SEED, PRESETS, RAG_AMBER, RAG_GREEN, WEEK_DAYS
from planpilot.engine.schedule import EPS, cpm
from planpilot.models import Project

PROGRESS_COLUMNS = ["week", "task_id", "actual_pct", "actual_cost"]
DURATION_NOISE = 0.15  # actual duration = m x slip x U(1 - noise, 1 + noise)
COST_NOISE = 0.05  # actual cost factor = cost_overrun x U(1 - noise, 1 + noise)
DURATION_STREAM, COST_STREAM = 2000, 3000  # separate from the Monte Carlo streams


@dataclass
class EVMStatus:
    week: int
    bac: float
    pv: float
    ev: float
    ac: float
    spi: float
    cpi: float
    eac: float
    vac: float
    rag: str


def budgets(project: Project) -> dict[str, float]:
    rates = PRESETS[project.environment].rates
    return {t.id: t.most_likely * rates[t.role] for t in project.tasks}


def planned_weeks(project: Project) -> int:
    return math.ceil(cpm(project).duration / WEEK_DAYS - EPS)


def default_as_of_week(project: Project) -> int:
    return max(1, round(AS_OF_SHARE * cpm(project).duration / WEEK_DAYS))


def _pct(t: float, es: float, ef: float) -> float:
    """Linear progress between start and finish; a zero-length task is done once reached."""
    if ef - es <= EPS:
        return 1.0 if t >= es - EPS else 0.0
    return float(np.clip((t - es) / (ef - es), 0.0, 1.0))


def planned_pct(project: Project, week: int) -> dict[str, float]:
    """Planned share complete per task at the end of `week` (linear between CPM ES and EF)."""
    sched = cpm(project)
    t = week * WEEK_DAYS
    return {tid: _pct(t, sched.es[tid], sched.ef[tid]) for tid in sched.order}


def planned_value(project: Project, week: int) -> float:
    b = budgets(project)
    return sum(pct * b[tid] for tid, pct in planned_pct(project, week).items())


def planned_curve(project: Project) -> pd.DataFrame:
    """PV per week over the whole plan, from week 0 to completion (PV reaches BAC)."""
    weeks = range(planned_weeks(project) + 1)
    return pd.DataFrame({"week": list(weeks), "pv": [planned_value(project, w) for w in weeks]})


def _uniform(seed: int, stream: int) -> float:
    return float(np.random.default_rng([seed, stream]).random())


def simulate_progress(
    project: Project,
    as_of_week: int,
    slip: float = 1.0,
    cost_overrun: float = 1.0,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """Synthetic cumulative progress for weeks 1..as_of_week, built from the given plan.

    Each task's actual duration is m x slip x noise; a CPM pass on those durations gives the
    actual start and finish, so delays push successors back. Slip stretches elapsed time
    only; spend is actual % x budget x cost_overrun x noise.
    """
    b = budgets(project)
    actual: dict[str, float] = {}
    cost_factor: dict[str, float] = {}
    for t in project.tasks:
        num = int(t.id[1:])
        u = _uniform(seed, DURATION_STREAM + num)
        actual[t.id] = t.most_likely * slip * (1 + DURATION_NOISE * (2 * u - 1))
        v = _uniform(seed, COST_STREAM + num)
        cost_factor[t.id] = cost_overrun * (1 + COST_NOISE * (2 * v - 1))
    sched = cpm(project, durations=actual)

    rows = []
    for week in range(1, as_of_week + 1):
        t = week * WEEK_DAYS
        for tid in sched.order:
            pct = round(_pct(t, sched.es[tid], sched.ef[tid]), 4)
            rows.append((week, tid, pct, round(pct * b[tid] * cost_factor[tid], 2)))
    return pd.DataFrame(rows, columns=PROGRESS_COLUMNS)


def evm_series(project: Project, progress: pd.DataFrame) -> pd.DataFrame:
    """PV, EV, AC, SPI, CPI, EAC and VAC for each week in `progress`.

    SPI = EV/PV, CPI = EV/AC, EAC = BAC/CPI, VAC = BAC - EAC. Indices are NaN when their
    denominator is 0.
    """
    b = budgets(project)
    bac = sum(b.values())
    df = progress.assign(ev=progress["actual_pct"] * progress["task_id"].map(b))
    weekly = (
        df.groupby("week")
        .agg(ev=("ev", "sum"), ac=("actual_cost", "sum"))
        .reset_index()
        .sort_values("week")
    )
    weekly["pv"] = [planned_value(project, int(w)) for w in weekly["week"]]
    weekly["spi"] = weekly["ev"] / weekly["pv"].replace(0, np.nan)
    weekly["cpi"] = weekly["ev"] / weekly["ac"].replace(0, np.nan)
    weekly["eac"] = bac / weekly["cpi"].replace(0, np.nan)
    weekly["vac"] = bac - weekly["eac"]
    return weekly[["week", "pv", "ev", "ac", "spi", "cpi", "eac", "vac"]].reset_index(drop=True)


def rag(spi: float, cpi: float, green: float = RAG_GREEN, amber: float = RAG_AMBER) -> str:
    """Green if both indices >= green, amber if the lower is >= amber, otherwise red."""
    lower = min(spi, cpi)
    if lower >= green:
        return "green"
    if lower >= amber:
        return "amber"
    return "red"


def status_at(project: Project, progress: pd.DataFrame) -> EVMStatus:
    """EVM figures at the last week in `progress` (the status date)."""
    last = evm_series(project, progress).iloc[-1]
    return EVMStatus(
        week=int(last["week"]),
        bac=sum(budgets(project).values()),
        pv=float(last["pv"]),
        ev=float(last["ev"]),
        ac=float(last["ac"]),
        spi=float(last["spi"]),
        cpi=float(last["cpi"]),
        eac=float(last["eac"]),
        vac=float(last["vac"]),
        rag=rag(float(last["spi"]), float(last["cpi"])),
    )


def task_progress(project: Project, progress: pd.DataFrame) -> pd.DataFrame:
    """Per task at the status date: planned vs actual %, PV, EV, AC and SV, worst SV first."""
    week = int(progress["week"].max())
    b = budgets(project)
    planned = planned_pct(project, week)
    critical = set(cpm(project).critical)
    now = progress[progress["week"] == week].set_index("task_id")
    rows = []
    for t in project.tasks:
        actual = float(now["actual_pct"].get(t.id, 0.0))
        rows.append(
            {
                "id": t.id,
                "name": t.name,
                "role": t.role,
                "critical": t.id in critical,
                "planned_pct": planned[t.id],
                "actual_pct": actual,
                "pv": planned[t.id] * b[t.id],
                "ev": actual * b[t.id],
                "ac": float(now["actual_cost"].get(t.id, 0.0)),
            }
        )
    df = pd.DataFrame(rows)
    df["sv"] = df["ev"] - df["pv"]
    return df.sort_values(["sv", "id"]).reset_index(drop=True)
