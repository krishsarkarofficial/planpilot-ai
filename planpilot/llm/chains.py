"""Prompt chains: the LLM proposes, Pydantic and the plan checks verify."""

from datetime import date

import numpy as np
from pydantic import BaseModel

from planpilot.config import PRESETS, PROMPT_DIR
from planpilot.engine.schedule import check_plan
from planpilot.llm.client import LLMClient
from planpilot.models import Environment, Project, Task


class WBSDraft(BaseModel):
    name: str
    tasks: list[Task]


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
