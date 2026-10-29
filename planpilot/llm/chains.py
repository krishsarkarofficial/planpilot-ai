"""Prompt chains: the LLM proposes, Pydantic and the plan checks verify."""

from datetime import date

import numpy as np
from pydantic import BaseModel

from planpilot.config import PRESETS, PROMPT_DIR
from planpilot.engine.schedule import check_plan
from planpilot.llm.client import LLMClient
from planpilot.models import Environment, Project, Risk, Task

MIN_RISKS, MAX_RISKS = 8, 12


class WBSDraft(BaseModel):
    name: str
    tasks: list[Task]


class RiskDraft(BaseModel):
    risks: list[Risk]


def _example(kind: str, environment: str) -> str:
    return (PROMPT_DIR / "examples" / f"{kind}_{environment}.json").read_text(encoding="utf-8")


def assemble_project(
    draft: WBSDraft, environment: Environment, brief: str, start_date: date, deadline: date
) -> Project:
    """Combine LLM tasks with user inputs; raises ValidationError on structural problems."""
    return Project(
        name=draft.name,
        environment=environment,
        brief=brief,
        start_date=start_date,
        deadline=deadline,
        team=dict(PRESETS[environment].team),
        tasks=draft.tasks,
        risks=[],
    )


def plan_chain(
    client: LLMClient,
    environment: Environment,
    brief: str,
    start_date: date,
    deadline: date,
    use_cache: bool = True,
    temperature: float = 0.2,
) -> tuple[Project, list[str]]:
    """Brief -> validated Project (no risks yet) and its plan-check warnings."""

    def check(draft: WBSDraft) -> list[str]:
        project = assemble_project(draft, environment, brief, start_date, deadline)
        errors, _ = check_plan(project)
        return errors

    preset = PRESETS[environment]
    draft = client.complete_json(
        "wbs",
        {
            "environment_label": preset.label,
            "roles": ", ".join(preset.rates),
            "start_date": start_date.isoformat(),
            "deadline": deadline.isoformat(),
            "timeframe_days": int(np.busday_count(start_date, np.datetime64(deadline, "D") + 1)),
            "brief": brief,
            "example": _example("wbs", environment),
        },
        WBSDraft,
        use_cache=use_cache,
        temperature=temperature,
        check=check,
    )
    project = assemble_project(draft, environment, brief, start_date, deadline)
    _, warnings = check_plan(project)
    return project, warnings


def with_risks(project: Project, risks: list[Risk]) -> Project:
    """Copy of `project` with a new register, re-validated (unknown task ids or roles raise)."""
    data = project.model_dump()
    data["risks"] = [r.model_dump() for r in risks]
    return Project.model_validate(data)


def risk_chain(
    client: LLMClient,
    project: Project,
    use_cache: bool = True,
    temperature: float = 0.2,
) -> tuple[Project, list[str]]:
    """Project -> same project with an LLM-drafted, validated risk register, and warnings."""

    def check(draft: RiskDraft) -> list[str]:
        with_risks(project, draft.risks)
        n = len(draft.risks)
        return (
            [] if MIN_RISKS <= n <= MAX_RISKS else [f"{n} risks; expected {MIN_RISKS}-{MAX_RISKS}"]
        )

    preset = PRESETS[project.environment]
    tasks = "\n".join(
        f"{t.id} | {t.name} | {t.phase} | {t.role} | {t.most_likely:g}" for t in project.tasks
    )
    draft = client.complete_json(
        "risks",
        {
            "environment_label": preset.label,
            "roles": ", ".join(preset.rates),
            "name": project.name,
            "brief": project.brief,
            "tasks": tasks,
            "example": _example("risks", project.environment),
        },
        RiskDraft,
        use_cache=use_cache,
        temperature=temperature,
        check=check,
    )
    updated = with_risks(project, draft.risks)
    _, warnings = check_plan(updated)
    return updated, warnings
