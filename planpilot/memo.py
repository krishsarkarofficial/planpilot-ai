"""Decision memo inputs: the fact sheet given to the LLM, a code-written template memo and the
text the figure check runs on. The ranking is code's; the memo only explains it."""

from pydantic import BaseModel, Field

from planpilot.config import N_ITERATIONS, WEIGHT_SCENARIOS
from planpilot.engine.decision import BASELINE, CRITERIA, Comparison, describe_change
from planpilot.engine.schedule import finish_date
from planpilot.models import AddResource, CutScope, ExtendDeadline, MitigateRisk, Project
from planpilot.status import lakh

RECOMMENDATION_SCENARIO = "balanced"


class DecisionMemo(BaseModel):
    headline: str
    situation: str
    recommended_option: str
    recommendation: str
    rationale: list[str] = Field(min_length=1, max_length=4)
    trade_offs: list[str] = Field(min_length=1, max_length=3)
    sensitivity: str
    next_steps: list[str] = Field(min_length=1, max_length=4)


def fmt_metric(key: str, value: float) -> str:
    match key:
        case "prob_on_time":
            return f"{value:.0%}"
        case "cost":
            return lakh(value)
        case _:  # p50, p80, p90, spread: working days
            return f"{value:.1f} working days"


def _change_text(name: str, comparison: Comparison, project: Project) -> str:
    option = next(r.option for r in comparison.results if r.name == name)
    if not option.changes:
        return option.description
    return "; ".join(describe_change(c, project) for c in option.changes)


def memo_facts(project: Project, comparison: Comparison, seed: int) -> str:
    """Every figure the memo may use, precomputed and formatted by code."""
    m = comparison.metrics
    base = m.loc[BASELINE]
    lines = [
        f"Project: {project.name}",
        f"Start date: {project.start_date:%d %b %Y}; baseline deadline: "
        f"{project.deadline:%d %b %Y} ({int(base['deadline_days'])} working days)",
        f"Simulation: {N_ITERATIONS:,} runs, seed {seed}; every alternative uses the same "
        "random draws",
        "Alternatives (name | what changes):",
    ]
    for r in comparison.results:
        lines.append(f"{r.name} | {_change_text(r.name, comparison, project)}")
    lines.append(
        "Results (alternative | deadline | P50 finish | P80 finish | P90 finish | "
        "P80 finish date | probability of meeting the deadline | expected cost | "
        "spread P90-P50):"
    )
    for r in comparison.results:
        row = m.loc[r.name]
        lines.append(
            f"{r.name} | {r.project.deadline:%d %b %Y} | {fmt_metric('p50', row['p50'])} | "
            f"{fmt_metric('p80', row['p80'])} | {fmt_metric('p90', row['p90'])} | "
            f"{finish_date(r.project, row['p80']):%d %b %Y} | "
            f"{fmt_metric('prob_on_time', row['prob_on_time'])} | "
            f"{fmt_metric('cost', row['cost'])} | {fmt_metric('spread', row['spread'])}"
        )
    lines.append(
        "Change against the baseline (alternative | P80 finish | probability of meeting the "
        "deadline | expected cost):"
    )
    for r in comparison.results[1:]:
        row = m.loc[r.name]
        lines.append(
            f"{r.name} | {row['p80'] - base['p80']:+.1f} working days | "
            f"{round((row['prob_on_time'] - base['prob_on_time']) * 100):+d} percentage points | "
            f"{'+' if row['cost'] >= base['cost'] else '-'}{lakh(abs(row['cost'] - base['cost']))}"
        )
    lines.append(
        "Scores out of 1 per weight scenario (criteria weights: "
        + ", ".join(c.label for c in CRITERIA.values())
        + "):"
    )
    for scenario, weights in WEIGHT_SCENARIOS.items():
        ordered = comparison.scores[scenario].sort_values(ascending=False, kind="stable")
        lines.append(
            f"{scenario} | weights {', '.join(f'{w:.2f}' for w in weights.values())} | "
            + "; ".join(f"{name} {score:.2f}" for name, score in ordered.items())
            + f" | winner: {comparison.winners[scenario]}"
        )
    lines.append("Same winner under every scenario: " + ("yes" if comparison.stable else "no"))
    lines.append(
        f"Recommended alternative (winner under {RECOMMENDATION_SCENARIO} weights): "
        f"{comparison.winners[RECOMMENDATION_SCENARIO]}"
    )
    return "\n".join(lines)


def _next_step(change) -> str:
    match change:
        case AddResource():
            return (
                f"Project lead to confirm that {change.added_people} more people in the "
                f"{change.role} role can start on time."
            )
        case CutScope():
            return f"Sponsor to agree in writing to drop {', '.join(change.task_ids)}."
        case MitigateRisk():
            return f"Risk owners to start the mitigation for {', '.join(change.risk_ids)}."
        case ExtendDeadline():
            return (
                f"Project lead to ask the sponsor to move the deadline by {change.days} "
                "working days."
            )


def template_memo(project: Project, comparison: Comparison) -> DecisionMemo:
    """The decision memo written by code from the same figures (no LLM)."""
    winner = comparison.winners[RECOMMENDATION_SCENARIO]
    m = comparison.metrics
    base, best = m.loc[BASELINE], m.loc[winner]
    option = next(r.option for r in comparison.results if r.name == winner)
    keys = ["p80", "prob_on_time", "cost"]

    rationale = [
        f"{CRITERIA[k].label}: {fmt_metric(k, best[k])} against {fmt_metric(k, base[k])} "
        "for the baseline."
        for k in keys
    ]
    if winner == BASELINE:
        rationale = ["No option improves enough on the baseline under the balanced weights."]

    trade_offs = []
    for key, criterion in CRITERIA.items():
        better = m[key].idxmax() if criterion.higher_is_better else m[key].idxmin()
        if better != winner and m.loc[better, key] != best[key]:
            trade_offs.append(
                f"{better} is better on {criterion.phrase} "
                f"({fmt_metric(key, m.loc[better, key])} against {fmt_metric(key, best[key])})."
            )
    trade_offs = trade_offs[:3] or ["No alternative beats it on any single criterion."]

    if comparison.stable:
        sensitivity = f"{winner} ranks first under every weighting."
    else:
        sensitivity = (
            "The ranking depends on the weights ("
            + "; ".join(f"{s}: {w}" for s, w in comparison.winners.items())
            + ")."
        )

    next_steps = [_next_step(c) for c in option.changes][:3] or [
        "Keep the plan and review the risk register every week."
    ]
    next_steps.append("Re-run this comparison after the next weekly status report.")

    return DecisionMemo(
        headline=(
            f"Recommend: {winner}. {fmt_metric('prob_on_time', best['prob_on_time'])} chance "
            f"of meeting the deadline against {fmt_metric('prob_on_time', base['prob_on_time'])}."
        ),
        situation=(
            f"Without changes there is a {fmt_metric('prob_on_time', base['prob_on_time'])} "
            f"chance of finishing by {project.deadline:%d %b %Y}. The P80 finish is "
            f"{fmt_metric('p80', base['p80'])} and the expected cost is "
            f"{fmt_metric('cost', base['cost'])}."
        ),
        recommended_option=winner,
        recommendation=(
            f"Choose {winner}. It scores {comparison.scores[RECOMMENDATION_SCENARIO][winner]:.2f} "
            f"out of 1 under the {RECOMMENDATION_SCENARIO} weights, the highest of all "
            "alternatives."
        ),
        rationale=rationale,
        trade_offs=trade_offs,
        sensitivity=sensitivity,
        next_steps=next_steps[:4],
    )


def memo_text(memo: DecisionMemo) -> str:
    return "\n".join(
        [memo.headline, memo.situation, memo.recommended_option, memo.recommendation]
        + memo.rationale
        + memo.trade_offs
        + [memo.sensitivity]
        + memo.next_steps
    )
