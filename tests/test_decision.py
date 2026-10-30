from datetime import date

import numpy as np
import pytest
from factories import make_project, risk

from planpilot.config import WEIGHT_SCENARIOS
from planpilot.engine.decision import (
    BASELINE,
    CRITERIA,
    apply_option,
    compare,
    evaluate,
    normalise,
    suggest_options,
)
from planpilot.engine.montecarlo import simulate
from planpilot.models import (
    AddResource,
    CutScope,
    ExtendDeadline,
    MitigateRisk,
    Option,
)
from planpilot.samples import available_samples, demo_options, load_options, load_sample

DIAMOND = [
    ("T01", "A", (2, 3, 5), []),
    ("T02", "A", (1, 2, 4), ["T01"]),
    ("T03", "B", (3, 4, 8), ["T01"]),
    ("T04", "B", (1, 1, 2), ["T02", "T03"]),
]
CHAIN = [
    ("T01", "A", 2, []),
    ("T02", "A", 3, ["T01"]),
    ("T03", "B", 4, ["T02"]),
    ("T04", "B", 5, ["T03"]),
]
SEED = 3


def option(*changes) -> Option:
    return Option(name="opt", description="", changes=list(changes))


def diamond(**kw):
    r = risk("R01", probability=0.6, impact=3, tasks=("T03",))
    return make_project(DIAMOND, risks=[r], **kw)


def test_cut_scope_reduces_p80_and_rewires_dependents():
    p = diamond()
    applied = apply_option(p, option(CutScope(task_ids=["T03"])))
    t04 = next(t for t in applied.project.tasks if t.id == "T04")
    assert t04.depends_on == ["T02", "T01"]  # T03's predecessor T01 takes its place
    assert len(applied.project.tasks) == 3
    assert applied.project.risks == []  # R01 only affected the cut task
    base, cut = simulate(p, seed=SEED), simulate(applied.project, seed=SEED)
    assert cut.percentile(80) < base.percentile(80)


def test_cut_scope_resolves_chains_and_keeps_partly_affected_risks():
    p = make_project(
        CHAIN,
        risks=[risk("R01", tasks=("T02",)), risk("R02", tasks=("T02", "T04"))],
    )
    applied = apply_option(p, option(CutScope(task_ids=["T02", "T03"]))).project
    assert [(t.id, t.depends_on) for t in applied.tasks] == [("T01", []), ("T04", ["T01"])]
    assert [(r.id, r.affected_task_ids) for r in applied.risks] == [("R02", ["T04"])]


def test_extend_deadline_raises_probability_by_working_days():
    p = diamond(deadline=date(2026, 11, 13))
    ext = apply_option(p, option(ExtendDeadline(days=3))).project
    assert ext.deadline == date(2026, 11, 18)  # Fri 13 Nov + 3 working days = Wed 18 Nov
    base, longer = simulate(p, seed=SEED), simulate(ext, seed=SEED)
    assert longer.deadline_days == base.deadline_days + 3
    assert 0 < base.prob_on_time < longer.prob_on_time <= 1
    assert np.array_equal(base.durations, longer.durations)  # only the deadline moved


def test_mitigate_risk_lowers_p80_and_p90_and_adds_its_cost():
    p = diamond()
    change = MitigateRisk(risk_ids=["R01"], probability_multiplier=0.5, cost=1000)
    applied = apply_option(p, option(change))
    assert applied.project.risks[0].probability == pytest.approx(0.3)
    assert applied.fixed_cost == 1000
    base = simulate(p, seed=SEED)
    mitigated = simulate(applied.project, seed=SEED, fixed_cost=applied.fixed_cost)
    for q in (80, 90):  # not the spread: a frequent risk also shifts P50 (see PLAN.md, P3)
        assert mitigated.percentile(q) <= base.percentile(q)
    assert mitigated.percentile(80) < base.percentile(80)


def test_add_resource_shortens_the_roles_tasks_and_raises_cost():
    p = make_project(DIAMOND)  # one developer, e = 0.6: tasks take 1 / (1 + 0.6) of the time
    more_dev = option(AddResource(role="developer", added_people=1))
    applied = apply_option(p, more_dev)
    assert applied.project.team["developer"] == 2
    assert applied.project.tasks[1].most_likely == pytest.approx(2 / 1.6)
    base = evaluate(p, Option(name="base", description=""), seed=SEED)
    more = evaluate(p, more_dev, seed=SEED)
    assert more.sim.task_durations.mean() == pytest.approx(
        base.sim.task_durations.mean() / 1.6, rel=1e-6
    )
    assert more.sim.percentile(80) < base.sim.percentile(80)
    assert more.sim.costs.mean() > base.sim.costs.mean()


def test_add_resource_divides_by_current_headcount():
    p = make_project(DIAMOND).model_copy(update={"team": {"developer": 3}})
    t = apply_option(p, option(AddResource(role="developer", added_people=3))).project.tasks[0]
    assert t.most_likely == pytest.approx(3 / (1 + 0.6 * 3 / 3))


@pytest.mark.parametrize(
    "change, match",
    [
        (CutScope(task_ids=["T99"]), "unknown tasks T99"),
        (CutScope(task_ids=["T01", "T02", "T03", "T04"]), "every task"),
        (MitigateRisk(risk_ids=["R99"], probability_multiplier=0.5), "unknown risks R99"),
        (AddResource(role="pilot", added_people=1), "unknown role"),
        (AddResource(role="tester", added_people=1), "no task needs"),
    ],
)
def test_bad_changes_raise(change, match):
    with pytest.raises(ValueError, match=match):
        apply_option(diamond(), option(change))


def test_apply_option_does_not_touch_the_project():
    p = diamond()
    before = p.model_dump()
    apply_option(p, option(CutScope(task_ids=["T03"]), ExtendDeadline(days=2)))
    assert p.model_dump() == before


def test_weight_scenarios_sum_to_one_and_cover_every_criterion():
    assert set(WEIGHT_SCENARIOS) == {"balanced", "schedule-first", "cost-first"}
    for weights in WEIGHT_SCENARIOS.values():
        assert set(weights) == set(CRITERIA)
        assert sum(weights.values()) == pytest.approx(1.0)


def test_normalise_inverts_lower_is_better_and_handles_ties():
    assert normalise([10, 20, 30], higher_is_better=False) == [1.0, 0.5, 0.0]
    assert normalise([0.2, 0.6], higher_is_better=True) == [0.0, 1.0]
    assert normalise([5, 5, 5], higher_is_better=False) == [1.0, 1.0, 1.0]


def test_compare_uses_common_random_numbers_and_ranks_the_baseline():
    p = diamond(deadline=date(2026, 11, 13))
    options = [
        Option(name="cut", description="", changes=[CutScope(task_ids=["T03"])]),
        Option(name="later", description="", changes=[ExtendDeadline(days=3)]),
    ]
    c = compare(p, options, seed=SEED)
    assert list(c.metrics.index) == [BASELINE, "cut", "later"]
    base = simulate(p, seed=SEED)
    assert np.array_equal(c.results[0].sim.durations, base.durations)
    assert np.array_equal(c.results[2].sim.durations, base.durations)  # only the deadline moved
    assert c.metrics.loc["later", "prob_on_time"] > c.metrics.loc[BASELINE, "prob_on_time"]
    assert set(c.scores) == set(WEIGHT_SCENARIOS) and set(c.winners) == set(WEIGHT_SCENARIOS)
    assert all(0 <= s <= 1 for v in c.scores.values() for s in v)
    again = compare(p, options, seed=SEED)
    assert again.winners == c.winners and again.metrics.equals(c.metrics)


def test_compare_rejects_duplicate_names():
    with pytest.raises(ValueError, match="unique"):
        compare(diamond(), [Option(name=BASELINE, description="")])


@pytest.mark.parametrize("env", available_samples())
def test_demo_options_apply_to_their_frozen_project(env):
    project = load_sample(env)
    options = load_options(env)
    assert len(options) == 3 and demo_options(project) == options
    assert len(compare(project, options, n=500).results) == 4
    assert demo_options(project.model_copy(update={"name": "edited"})) is None


@pytest.mark.parametrize("env", available_samples())
def test_suggested_options_work_for_any_project(env):
    project = load_sample(env)
    options = suggest_options(project, simulate(project, n=1000))
    assert {c.type for o in options for c in o.changes} == {
        "add_resource",
        "mitigate_risk",
        "extend_deadline",
    }
    assert len(compare(project, options, n=500).results) == 4
