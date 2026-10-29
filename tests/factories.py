"""Small synthetic projects for tests."""

from datetime import date

from planpilot.models import Project, Risk


def make_project(tasks: list[tuple], deadline=date(2026, 12, 31), risks=()) -> Project:
    """tasks: (id, phase, estimate, depends_on); estimate is m (o=m, p=m+1) or (o, m, p)."""
    rows = []
    for tid, phase, est, deps in tasks:
        o, m, p = est if isinstance(est, tuple) else (est, est, est + 1)
        rows.append(
            {
                "id": tid,
                "name": tid,
                "phase": phase,
                "role": "developer",
                "optimistic": o,
                "most_likely": m,
                "pessimistic": p,
                "depends_on": deps,
            }
        )
    return Project(
        name="test",
        environment="software",
        brief="",
        start_date=date(2026, 11, 2),  # Monday
        deadline=deadline,
        team={"developer": 1},
        tasks=rows,
        risks=list(risks),
    )


def risk(rid: str, category: str = "technical", probability=0.5, impact=1, tasks=("T01",)) -> Risk:
    return Risk(
        id=rid,
        title=rid,
        category=category,
        cause="c",
        event="e",
        effect="f",
        probability=probability,
        impact_days=impact,
        affected_task_ids=list(tasks),
        owner_role="developer",
        response_strategy="accept",
        response="r",
    )
