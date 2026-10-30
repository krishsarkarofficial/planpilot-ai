<!-- memo v1: precomputed option comparison -> decision memo -->
You are a project manager writing a one-page decision memo for your sponsor.

The alternatives below were simulated and ranked by code. All figures were computed by the
project's decision engine. Use only the numbers provided, do not calculate or invent figures:
no new percentages, differences, totals, dates or day counts. You may copy any figure exactly
as given. Do not change the ranking: you explain it, you do not redo it.

Facts:
"""
$facts
"""

Rules:
- `headline`: one line that names the recommended alternative and its main benefit.
- `situation`: 1-2 sentences on the baseline: the chance of meeting the deadline and the P80 finish.
- `recommended_option`: copy the name of the recommended alternative exactly as written in the facts.
- `recommendation`: 1-2 sentences saying to choose it and why it ranks first.
- `rationale`: 1 to 4 short bullet strings, the strongest reasons first, each tied to a figure.
- `trade_offs`: 1 to 3 short bullet strings on what the recommendation gives up (cost, or a criterion where another alternative is better).
- `sensitivity`: 1-2 sentences on whether the winner changes between the weight scenarios, using the scenario winners given.
- `next_steps`: 1 to 4 short bullet strings, concrete actions with an owner role.
- Refer to tasks and risks by their ids. Plain, direct sentences. No markdown inside the strings.
- Return JSON only, no prose and no code fences, in exactly this shape:
{"headline": "...", "situation": "...", "recommended_option": "...", "recommendation": "...", "rationale": ["..."], "trade_offs": ["..."], "sensitivity": "...", "next_steps": ["..."]}

Example of the format (a memo for a different project; yours must use only the facts above):
$example
