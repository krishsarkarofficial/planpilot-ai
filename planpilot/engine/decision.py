"""Decision options: apply changes to a project, re-simulate with the same seed, score.

Every alternative (the baseline included) is simulated with the same seed, and each task and
risk has its own random stream (see montecarlo.py), so differences between alternatives come
from the option and not from sampling noise.
"""

from dataclasses import dataclass
from datetime import date
from math import ceil

import numpy as np
import pandas as pd

from planpilot.config import DEFAULT_SEED, N_ITERATIONS, PRESETS, WEIGHT_SCENARIOS
from planpilot.engine.montecarlo import SimResult, simulate
from planpilot.models import (
    AddResource,
    Change,
    CutScope,
    ExtendDeadline,
    MitigateRisk,
    Option,
    Project,
)

BASELINE = "Baseline (no change)"
MITIGATION_DAYS = 3  # suggest_options: one-off cost of a mitigation, in days of the owner's rate
MITIGATION_FACTOR = 0.5
MIN_EXTENSION_DAYS = 5
SUGGESTED_RISKS = 3


@dataclass(frozen=True)
class Criterion:
    label: str
    higher_is_better: bool
    phrase: str  # mid-sentence wording


CRITERIA: dict[str, Criterion] = {
    "p80": Criterion("P80 finish", False, "P80 finish"),
    "prob_on_time": Criterion(
        "Probability of meeting the deadline", True, "the probability of meeting the deadline"
    ),
    "cost": Criterion("Expected cost", False, "expected cost"),
    "spread": Criterion("Spread (P90 - P50)", False, "spread"),
}


@dataclass
class Applied:
    project: Project
    rates: dict[str, float]
    fixed_cost: float


@dataclass
class OptionResult:
    option: Option
    project: Project  # the project with the option applied
    fixed_cost: float
    sim: SimResult

    @property
    def name(self) -> str:
        return self.option.name

    def metrics(self) -> dict[str, float]:
        p50, p80, p90 = (self.sim.percentile(q) for q in (50, 80, 90))
        return {
            "p50": p50,
            "p80": p80,
            "p90": p90,
            "prob_on_time": self.sim.prob_on_time,
            "cost": float(self.sim.costs.mean()),
            "spread": p90 - p50,
            "deadline_days": float(self.sim.deadline_days),
        }


@dataclass
class Comparison:
    results: list[OptionResult]  # baseline first
    metrics: pd.DataFrame  # one row per alternative, raw values
    scores: dict[str, pd.Series]  # scenario -> weighted score per alternative
    winners: dict[str, str]  # scenario -> best alternative

    @property
    def stable(self) -> bool:
        return len(set(self.winners.values())) == 1


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _add_resource(
    data: dict, team: dict[str, int], added: dict[str, int], change: AddResource
) -> None:
    if change.role not in PRESETS[data["environment"]].rates:
        raise ValueError(f"add_resource: unknown role '{change.role}'")
    tasks = [t for t in data["tasks"] if t["role"] == change.role]
    if not tasks:
        raise ValueError(f"add_resource: no task needs the role '{change.role}'")
    n = max(team.get(change.role, 0), 1)
    factor = 1 / (1 + change.efficiency * change.added_people / n)
    for t in tasks:
        for field in ("optimistic", "most_likely", "pessimistic"):
            t[field] *= factor
    team[change.role] = team.get(change.role, 0) + change.added_people
    added[change.role] = added.get(change.role, 0) + change.added_people


def _cut_scope(data: dict, change: CutScope) -> None:
    cut = set(change.task_ids)
    deps = {t["id"]: t["depends_on"] for t in data["tasks"]}
    unknown = sorted(cut - set(deps))
    if unknown:
        raise ValueError(f"cut_scope: unknown tasks {', '.join(unknown)}")
    if cut == set(deps):
        raise ValueError("cut_scope: cannot cut every task")

    def resolve(tid: str) -> list[str]:
        """Kept tasks that stand in for `tid`: itself, or the predecessors of a cut task."""
        if tid not in cut:
            return [tid]
        return [k for d in deps[tid] for k in resolve(d)]

    data["tasks"] = [
        {**t, "depends_on": _dedupe([k for d in t["depends_on"] for k in resolve(d)])}
        for t in data["tasks"]
        if t["id"] not in cut
    ]
    risks = []
    for r in data["risks"]:
        kept = [tid for tid in r["affected_task_ids"] if tid not in cut]
        if kept:  # a risk that only affected cut tasks disappears with them
            risks.append({**r, "affected_task_ids": kept})
    data["risks"] = risks


def _mitigate_risk(data: dict, change: MitigateRisk) -> None:
    by_id = {r["id"]: r for r in data["risks"]}
    unknown = sorted(set(change.risk_ids) - set(by_id))
    if unknown:
        raise ValueError(f"mitigate_risk: unknown risks {', '.join(unknown)}")
    for rid in _dedupe(change.risk_ids):
        by_id[rid]["probability"] *= change.probability_multiplier


def apply_option(project: Project, option: Option) -> Applied:
    """The project with every change applied in order, validated again, plus cost inputs.

    - add_resource: that role's tasks take 1 / (1 + e k / n) of their time (n = headcount before
      the change); the role is charged (1 + k) x its rate. Risk delays are not shortened.
    - cut_scope: dependents take over the cut task's predecessors; risks lose the cut tasks.
    - mitigate_risk: probabilities are multiplied; the one-off cost is added to the total.
    - extend_deadline: moves the deadline by working days.
    """
    data = project.model_dump()
    team = dict(project.team)
    added: dict[str, int] = {}
    fixed_cost = 0.0
    for change in option.changes:
        match change:
            case AddResource():
                _add_resource(data, team, added, change)
            case CutScope():
                _cut_scope(data, change)
            case MitigateRisk():
                _mitigate_risk(data, change)
                fixed_cost += change.cost
            case ExtendDeadline():
                moved = np.busday_offset(np.datetime64(data["deadline"], "D"), change.days)
                data["deadline"] = moved.astype(date)
    data["team"] = team
    rates = {
        role: rate * (1 + added.get(role, 0))
        for role, rate in PRESETS[project.environment].rates.items()
    }
    return Applied(Project.model_validate(data), rates, fixed_cost)


def evaluate(
    project: Project, option: Option, seed: int = DEFAULT_SEED, n: int = N_ITERATIONS
) -> OptionResult:
    applied = apply_option(project, option)
    sim = simulate(
        applied.project, seed=seed, n=n, rates=applied.rates, fixed_cost=applied.fixed_cost
    )
    return OptionResult(option, applied.project, applied.fixed_cost, sim)


def normalise(values: list[float], higher_is_better: bool) -> list[float]:
    """Min-max to 0-1 where 1 is best. If every alternative ties, all get 1."""
    lo, hi = min(values), max(values)
    if hi - lo <= 1e-9:
        return [1.0] * len(values)
    scaled = [(v - lo) / (hi - lo) for v in values]
    return scaled if higher_is_better else [1 - s for s in scaled]


def normalised_frame(metrics: pd.DataFrame) -> pd.DataFrame:
    """Per-criterion 0-1 scores (1 = best) for each alternative."""
    return pd.DataFrame(
        {key: normalise(list(metrics[key]), c.higher_is_better) for key, c in CRITERIA.items()},
        index=metrics.index,
    )


def weighted_scores(normalised: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    return sum(normalised[key] * w for key, w in weights.items())


def compare(
    project: Project,
    options: list[Option],
    seed: int = DEFAULT_SEED,
    n: int = N_ITERATIONS,
) -> Comparison:
    """Simulate the baseline and every option with the same seed and rank them under each
    weight scenario. Ties go to the earlier alternative (the baseline first)."""
    names = [BASELINE] + [o.name for o in options]
    if len(set(names)) != len(names):
        raise ValueError(f"option names must be unique and not '{BASELINE}'")
    alternatives = [Option(name=BASELINE, description="Keep the plan as it is.")] + options
    results = [evaluate(project, o, seed, n) for o in alternatives]
    metrics = pd.DataFrame([r.metrics() for r in results], index=names)
    normalised = normalised_frame(metrics)
    scores = {s: weighted_scores(normalised, w) for s, w in WEIGHT_SCENARIOS.items()}
    winners = {s: str(v.round(12).idxmax()) for s, v in scores.items()}
    return Comparison(results, metrics, scores, winners)


def describe_change(change: Change, project: Project) -> str:
    match change:
        case AddResource():
            return (
                f"add {change.added_people} people to the {change.role} role "
                f"(efficiency {change.efficiency:g})"
            )
        case CutScope():
            names = "; ".join(
                f"{t.id} {t.name}" for t in project.tasks if t.id in set(change.task_ids)
            )
            return f"cut scope: {names}"
        case MitigateRisk():
            cost = f", one-off cost ₹{change.cost / 1e5:.2f} lakh" if change.cost else ""
            return (
                f"mitigate {', '.join(change.risk_ids)} "
                f"(probability x {change.probability_multiplier:g}{cost})"
            )
        case ExtendDeadline():
            return f"extend the deadline by {change.days} working days"


def suggest_options(project: Project, res: SimResult) -> list[Option]:
    """Three generic options for any project, chosen from the baseline simulation: more people
    on the role carrying the most critical work, mitigation of the risks that threaten the
    critical path, and a deadline moved to about the baseline P80."""
    rates = PRESETS[project.environment].rates
    load: dict[str, float] = {}
    for t in project.tasks:
        load[t.role] = load.get(t.role, 0.0) + res.criticality[t.id] * t.most_likely
    role = max(load, key=lambda r: load[r])

    def threat(r) -> float:
        crit = np.mean([res.criticality[tid] for tid in r.affected_task_ids])
        return r.probability * r.impact_days * float(crit)

    label = role.replace("_", " ")
    options = [
        Option(
            name=f"Add one {label}",
            description=f"Bring one more {label} to the role with the most critical work.",
            changes=[AddResource(role=role, added_people=1)],
        )
    ]
    top = sorted(project.risks, key=threat, reverse=True)[:SUGGESTED_RISKS]
    if top:
        cost = sum(MITIGATION_DAYS * rates[r.owner_role] for r in top)
        options.append(
            Option(
                name="Mitigate the top risks",
                description="Spend on prevention for the risks that threaten the critical path.",
                changes=[
                    MitigateRisk(
                        risk_ids=[r.id for r in top],
                        probability_multiplier=MITIGATION_FACTOR,
                        cost=cost,
                    )
                ],
            )
        )
    days = max(MIN_EXTENSION_DAYS, ceil(res.percentile(80) - res.deadline_days))
    options.append(
        Option(
            name=f"Extend the deadline by {days} days",
            description="Negotiate a later deadline with the sponsor.",
            changes=[ExtendDeadline(days=days)],
        )
    )
    return options
