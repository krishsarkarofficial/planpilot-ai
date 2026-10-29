"""Vectorised Monte Carlo schedule and cost simulation.

Random numbers are keyed by task and risk id (common random numbers): the same seed gives
the same draws for a task or risk in every option, even when other tasks are cut.
"""

from dataclasses import dataclass

import numpy as np

from planpilot.config import DEFAULT_SEED, N_ITERATIONS, PRESETS
from planpilot.engine.schedule import EPS, deadline_days, successors
from planpilot.models import Project, topological_order

RISK_STREAM_OFFSET = 1000


@dataclass
class SimResult:
    task_ids: list[str]
    task_durations: np.ndarray  # (n, tasks), including risk impacts
    durations: np.ndarray  # (n,) project duration in working days
    costs: np.ndarray  # (n,) INR
    deadline_days: int
    criticality: dict[str, float]  # share of iterations on the critical path
    tornado: dict[str, float]  # correlation of task duration with project duration

    def percentile(self, q: float, of: str = "duration") -> float:
        return float(np.percentile(self.durations if of == "duration" else self.costs, q))

    @property
    def prob_on_time(self) -> float:
        return float(np.mean(self.durations <= self.deadline_days + EPS))


def triangular_from_uniform(u: np.ndarray, o: float, m: float, p: float) -> np.ndarray:
    """Inverse CDF of the triangular distribution; constant when o == p."""
    if p == o:
        return np.full_like(u, o)
    fc = (m - o) / (p - o)
    low = o + np.sqrt(u * (p - o) * (m - o))
    high = p - np.sqrt((1 - u) * (p - o) * (p - m))
    return np.where(u < fc, low, high)


def _uniforms(seed: int, stream: int, n: int) -> np.ndarray:
    return np.random.default_rng([seed, stream]).random(n)


def simulate(
    project: Project,
    seed: int = DEFAULT_SEED,
    n: int = N_ITERATIONS,
    rates: dict[str, float] | None = None,
    fixed_cost: float = 0.0,
) -> SimResult:
    """Simulate project duration and cost.

    Cost = sum(sampled duration incl. risk delay x role rate) + fixed_cost.
    `rates` overrides the environment preset's daily rates (used by decision options).
    """
    rates = rates or PRESETS[project.environment].rates
    order = topological_order(project.tasks)
    tasks = {t.id: t for t in project.tasks}
    col = {tid: i for i, tid in enumerate(order)}

    dur = np.empty((n, len(order)))
    for tid in order:
        t = tasks[tid]
        u = _uniforms(seed, int(tid[1:]), n)
        dur[:, col[tid]] = triangular_from_uniform(u, t.optimistic, t.most_likely, t.pessimistic)

    for r in project.risks:
        fired = _uniforms(seed, RISK_STREAM_OFFSET + int(r.id[1:]), n) < r.probability
        for tid in r.affected_task_ids:
            dur[:, col[tid]] += fired * r.impact_days

    es = np.zeros_like(dur)
    ef = np.zeros_like(dur)
    for tid in order:
        i = col[tid]
        preds = [col[d] for d in tasks[tid].depends_on]
        if preds:
            es[:, i] = ef[:, preds].max(axis=1)
        ef[:, i] = es[:, i] + dur[:, i]
    total = ef.max(axis=1)

    succ = successors(project)
    ls = np.zeros_like(dur)
    for tid in reversed(order):
        i = col[tid]
        s = [col[x] for x in succ[tid]]
        lf = ls[:, s].min(axis=1) if s else total
        ls[:, i] = lf - dur[:, i]
    critical = (ls - es) <= EPS

    rate_vec = np.array([rates[tasks[tid].role] for tid in order])
    costs = dur @ rate_vec + fixed_cost

    return SimResult(
        task_ids=order,
        task_durations=dur,
        durations=total,
        costs=costs,
        deadline_days=deadline_days(project),
        criticality={tid: float(critical[:, col[tid]].mean()) for tid in order},
        tornado=_tornado(dur, total, order),
    )


def _tornado(dur: np.ndarray, total: np.ndarray, order: list[str]) -> dict[str, float]:
    """Pearson correlation of each task's duration with project duration (0 if constant)."""
    out: dict[str, float] = {}
    total_sd = total.std()
    for i, tid in enumerate(order):
        x = dur[:, i]
        if x.std() == 0 or total_sd == 0:
            out[tid] = 0.0
        else:
            out[tid] = float(np.corrcoef(x, total)[0, 1])
    return dict(sorted(out.items(), key=lambda kv: -abs(kv[1])))
