<!-- wbs v1: brief -> work breakdown structure with three-point estimates -->
You are an experienced project planner. Turn the project brief below into a work breakdown structure.

Environment: $environment_label
Allowed roles (use these exact strings, nothing else): $roles
Start date: $start_date
Deadline: $deadline ($timeframe_days working days available)

Brief:
"""
$brief
"""

Rules:
- 15 to 25 tasks, grouped into 4 to 6 phases; every phase has at least 2 tasks.
- Task ids are "T01", "T02", ... in order, with no gaps.
- Each task has one role from the allowed list.
- Durations are working days: optimistic <= most_likely <= pessimistic. Be realistic, not optimistic.
- `depends_on` lists ids of EARLIER tasks only (no cycles, no self-references).
- The plan must have at least two parallel paths (independent tasks that can run at the same time).
- Every task except the final one must be a predecessor of some later task.
- Do not compute dates, totals or schedules; only list tasks.
- Return JSON only, no prose and no code fences, in exactly this shape:
{"name": "<short project name>", "tasks": [{"id": "T01", "name": "...", "phase": "...", "role": "...", "optimistic": 2, "most_likely": 3, "pessimistic": 5, "depends_on": []}]}

Example of the format (a shorter plan for a different brief; your plan must follow the rules above):
$example
