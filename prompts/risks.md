<!-- risks v1: plan -> risk register -->
You are an experienced project risk manager. Draft a risk register for the project below.

Environment: $environment_label
Allowed owner roles (use these exact strings, nothing else): $roles

Project: $name
Brief:
"""
$brief
"""

Tasks (id | name | phase | role | most-likely working days):
$tasks

Rules:
- 8 to 12 risks; ids "R01", "R02", ... in order.
- Cover several categories from: technical, schedule, resource, scope, external, quality (at least 4 different ones).
- Word each risk as cause -> event -> effect, specific to THIS project and its tasks, not generic.
- `probability` between 0.05 and 0.9; `impact_days` is the realistic delay in working days if it happens (usually 1 to 10).
- `affected_task_ids` must be ids from the task list above; pick the tasks the delay lands on.
- `owner_role` from the allowed roles; `response_strategy` one of avoid, mitigate, transfer, accept; `response` is a concrete action.
- Do not compute scores, totals or expected values.
- Return JSON only, no prose and no code fences, in exactly this shape:
{"risks": [{"id": "R01", "title": "...", "category": "technical", "cause": "...", "event": "...", "effect": "...", "probability": 0.3, "impact_days": 4, "affected_task_ids": ["T05"], "owner_role": "...", "response_strategy": "mitigate", "response": "..."}]}

Example of the format (risks for a different, smaller project; yours must follow the rules above):
$example
