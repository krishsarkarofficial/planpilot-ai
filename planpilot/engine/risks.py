"""Risk scoring on a 5x5 probability-impact matrix."""

from bisect import bisect_left

import pandas as pd

from planpilot.models import Project

# Level n covers values up to and including the n-th edge; above the last edge is level 5.
PROBABILITY_EDGES = [0.1, 0.3, 0.5, 0.7]
IMPACT_EDGES = [1, 3, 5, 10]  # working days
LEVEL_LABELS = ["Very low", "Low", "Medium", "High", "Very high"]


def probability_level(p: float) -> int:
    return bisect_left(PROBABILITY_EDGES, p) + 1


def impact_level(days: float) -> int:
    return bisect_left(IMPACT_EDGES, days) + 1


def register_frame(project: Project) -> pd.DataFrame:
    """Risk register with code-computed levels, score (P x I) and expected delay (p x days)."""
    rows = [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "probability": r.probability,
            "impact_days": r.impact_days,
            "p_level": probability_level(r.probability),
            "i_level": impact_level(r.impact_days),
            "score": probability_level(r.probability) * impact_level(r.impact_days),
            "expected_delay": r.probability * r.impact_days,
            "affected": ", ".join(r.affected_task_ids),
            "owner": r.owner_role,
            "strategy": r.response_strategy,
            "cause": r.cause,
            "event": r.event,
            "effect": r.effect,
            "response": r.response,
        }
        for r in project.risks
    ]
    df = pd.DataFrame(rows, columns=list(rows[0]) if rows else None)
    if df.empty:
        return df
    return df.sort_values(["score", "expected_delay"], ascending=False).reset_index(drop=True)


def heatmap_cells(project: Project) -> dict[tuple[int, int], list[str]]:
    """(p_level, i_level) -> risk ids in that cell."""
    cells: dict[tuple[int, int], list[str]] = {}
    for r in project.risks:
        key = (probability_level(r.probability), impact_level(r.impact_days))
        cells.setdefault(key, []).append(r.id)
    return cells
