"""Status report inputs: the fact sheet given to the LLM, a code-written template report and
the check that the LLM used only figures from the fact sheet."""

import re

import pandas as pd
from pydantic import BaseModel, Field

from planpilot.config import WEEK_DAYS
from planpilot.engine.evm import planned_weeks, status_at, task_progress
from planpilot.engine.risks import register_frame
from planpilot.engine.schedule import cpm, working_day_to_date
from planpilot.models import Project

TOP_TASKS = 3
TOP_RISKS = 3
ID_PATTERN = re.compile(r"\b[TR]\d{2}\b")
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


class StatusReport(BaseModel):
    headline: str
    summary: str
    schedule: str
    cost: str
    issues: list[str] = Field(min_length=1, max_length=4)
    actions: list[str] = Field(min_length=1, max_length=4)


def lakh(x: float) -> str:
    return f"{'-' if x < 0 else ''}₹{abs(x) / 1e5:.2f} lakh"


def _behind(project: Project, progress: pd.DataFrame) -> pd.DataFrame:
    df = task_progress(project, progress)
    return df[df["actual_pct"] < df["planned_pct"] - 1e-9]


def status_facts(project: Project, progress: pd.DataFrame) -> str:
    """Every figure the status report may use, precomputed and formatted by code."""
    s = status_at(project, progress)
    behind = _behind(project, progress)
    as_of = working_day_to_date(project.start_date, s.week * WEEK_DAYS - 1)
    lines = [
        f"Project: {project.name}",
        f"Status date: end of week {s.week} ({as_of.astype(object):%d %b %Y})",
        f"Planned duration: {planned_weeks(project)} weeks "
        f"({cpm(project).duration:g} working days)",
        f"Overall status (RAG): {s.rag.upper()}",
        f"Budget at completion (BAC): {lakh(s.bac)}",
        f"Planned value (PV): {lakh(s.pv)}",
        f"Earned value (EV): {lakh(s.ev)}",
        f"Actual cost (AC): {lakh(s.ac)}",
        f"Planned complete: {s.pv / s.bac:.0%}",
        f"Actual complete: {s.ev / s.bac:.0%}",
        f"SPI: {s.spi:.2f}",
        f"CPI: {s.cpi:.2f}",
        f"Estimate at completion (EAC): {lakh(s.eac)}",
        f"Variance at completion (VAC): {lakh(s.vac)}"
        + (" (over budget)" if s.vac < 0 else " (under budget)"),
        f"Tasks behind plan: {len(behind)}",
        "Most behind (id | name | owner role | planned % | actual % | on critical path):",
    ]
    for r in behind.head(TOP_TASKS).itertuples():
        lines.append(
            f"{r.id} | {r.name} | {r.role} | {r.planned_pct:.0%} | {r.actual_pct:.0%} | "
            f"{'yes' if r.critical else 'no'}"
        )
    if behind.empty:
        lines.append("none")
    lines.append("Top risks (id | title | owner role | planned response):")
    for r in register_frame(project).head(TOP_RISKS).itertuples():
        lines.append(f"{r.id} | {r.title} | {r.owner} | {r.response}")
    if not project.risks:
        lines.append("none")
    return "\n".join(lines)


def template_status(project: Project, progress: pd.DataFrame) -> StatusReport:
    """The status report written by code from the same figures (no LLM)."""
    s = status_at(project, progress)
    behind = _behind(project, progress).head(TOP_TASKS)
    issues = [
        f"{r.id} {r.name} is {r.actual_pct:.0%} done against {r.planned_pct:.0%} planned"
        + (" and is on the critical path." if r.critical else ".")
        for r in behind.itertuples()
    ] or ["No task is behind plan."]
    actions = [
        f"{r.id}: the {r.role} lead agrees a recovery date for {r.name}."
        for r in behind.head(2).itertuples()
    ]
    actions += [f"{r.id}: {r.response}." for r in register_frame(project).head(1).itertuples()]
    return StatusReport(
        headline=f"{s.rag.upper()}: SPI {s.spi:.2f}, CPI {s.cpi:.2f} at the end of week {s.week}",
        summary=(
            f"The project has earned {lakh(s.ev)} of planned work against {lakh(s.pv)} "
            f"planned and has spent {lakh(s.ac)}."
        ),
        schedule=(
            f"SPI is {s.spi:.2f}: {s.ev / s.bac:.0%} of the work is complete against "
            f"{s.pv / s.bac:.0%} planned."
        ),
        cost=(
            f"CPI is {s.cpi:.2f}. At this rate the project will cost {lakh(s.eac)} against a "
            f"budget of {lakh(s.bac)}."
        ),
        issues=issues,
        actions=actions or ["Keep the current plan and review again next week."],
    )


def report_text(report: StatusReport) -> str:
    return "\n".join(
        [report.headline, report.summary, report.schedule, report.cost]
        + report.issues
        + report.actions
    )


def _numbers(text: str) -> list[str]:
    text = re.sub(r"(?<=\d),(?=\d)", "", ID_PATTERN.sub("", text))
    return NUMBER_PATTERN.findall(text)


def unknown_figures(report: StatusReport, facts: str) -> list[str]:
    """Numbers in the report that are not in the fact sheet (a rounded fact is allowed)."""
    allowed = [float(x) for x in _numbers(facts)]
    unknown = []
    for x in _numbers(report_text(report)):
        decimals = len(x.split(".")[1]) if "." in x else 0
        if not any(round(a, decimals) == float(x) for a in allowed):
            unknown.append(x)
    return sorted(set(unknown), key=float)
