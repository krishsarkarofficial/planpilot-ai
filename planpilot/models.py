"""Pydantic models for projects, tasks, risks and decision options."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from planpilot.config import DEFAULT_EFFICIENCY, PRESETS

Environment = Literal["software", "event", "construction"]
RiskCategory = Literal["technical", "schedule", "resource", "scope", "external", "quality"]
ResponseStrategy = Literal["avoid", "mitigate", "transfer", "accept"]


class Task(BaseModel):
    id: str = Field(pattern=r"^T\d{2}$")
    name: str
    phase: str
    role: str
    optimistic: float = Field(ge=0)
    most_likely: float = Field(ge=0)
    pessimistic: float = Field(gt=0)
    depends_on: list[str] = []

    @model_validator(mode="after")
    def _check_estimates(self) -> "Task":
        if not self.optimistic <= self.most_likely <= self.pessimistic:
            raise ValueError(
                f"{self.id}: estimates must satisfy optimistic <= most_likely <= pessimistic, "
                f"got {self.optimistic}, {self.most_likely}, {self.pessimistic}"
            )
        return self


class Risk(BaseModel):
    id: str = Field(pattern=r"^R\d{2}$")
    title: str
    category: RiskCategory
    cause: str
    event: str
    effect: str
    probability: float = Field(ge=0, le=1)
    impact_days: float = Field(ge=0)
    affected_task_ids: list[str] = Field(min_length=1)
    owner_role: str
    response_strategy: ResponseStrategy
    response: str


def topological_order(tasks: list[Task]) -> list[str]:
    """Task ids in dependency order (Kahn's algorithm). Raises ValueError on a cycle."""
    indegree = {t.id: len(t.depends_on) for t in tasks}
    successors: dict[str, list[str]] = {t.id: [] for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            successors[d].append(t.id)
    ready = [t.id for t in tasks if indegree[t.id] == 0]
    order: list[str] = []
    while ready:
        tid = ready.pop(0)
        order.append(tid)
        for s in successors[tid]:
            indegree[s] -= 1
            if indegree[s] == 0:
                ready.append(s)
    if len(order) < len(tasks):
        stuck = sorted(tid for tid, n in indegree.items() if n > 0)
        raise ValueError(f"dependency cycle among tasks: {', '.join(stuck)}")
    return order


class Project(BaseModel):
    name: str
    environment: Environment
    brief: str
    start_date: date
    deadline: date
    team: dict[str, int]
    tasks: list[Task] = Field(min_length=1)
    risks: list[Risk] = []

    @model_validator(mode="after")
    def _check_structure(self) -> "Project":
        task_ids = [t.id for t in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("duplicate task ids")
        risk_ids = [r.id for r in self.risks]
        if len(set(risk_ids)) != len(risk_ids):
            raise ValueError("duplicate risk ids")

        known = set(task_ids)
        for t in self.tasks:
            for d in t.depends_on:
                if d == t.id:
                    raise ValueError(f"{t.id} depends on itself")
                if d not in known:
                    raise ValueError(f"{t.id} depends on unknown task {d}")
        for r in self.risks:
            for tid in r.affected_task_ids:
                if tid not in known:
                    raise ValueError(f"{r.id} affects unknown task {tid}")

        roles = PRESETS[self.environment].rates
        for t in self.tasks:
            if t.role not in roles:
                raise ValueError(f"{t.id}: role '{t.role}' not in {self.environment} preset")
        for r in self.risks:
            if r.owner_role not in roles:
                raise ValueError(f"{r.id}: owner role '{r.owner_role}' not in preset")
        for role in self.team:
            if role not in roles:
                raise ValueError(f"team role '{role}' not in {self.environment} preset")

        if self.deadline < self.start_date:
            raise ValueError("deadline is before start_date")

        topological_order(self.tasks)
        return self


class AddResource(BaseModel):
    type: Literal["add_resource"] = "add_resource"
    role: str
    added_people: int = Field(ge=1)
    efficiency: float = Field(default=DEFAULT_EFFICIENCY, gt=0, le=1)


class CutScope(BaseModel):
    type: Literal["cut_scope"] = "cut_scope"
    task_ids: list[str] = Field(min_length=1)


class MitigateRisk(BaseModel):
    type: Literal["mitigate_risk"] = "mitigate_risk"
    risk_ids: list[str] = Field(min_length=1)
    probability_multiplier: float = Field(ge=0, le=1)
    cost: float = Field(default=0, ge=0)


class ExtendDeadline(BaseModel):
    type: Literal["extend_deadline"] = "extend_deadline"
    days: int = Field(ge=1)


Change = Annotated[
    AddResource | CutScope | MitigateRisk | ExtendDeadline, Field(discriminator="type")
]


class Option(BaseModel):
    name: str
    description: str
    changes: list[Change] = []
