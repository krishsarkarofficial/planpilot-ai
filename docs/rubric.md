# Plan quality rubric

There is no ground truth for what a good project plan is, so plan quality is judged against a
short rubric by a **single rater** (Krish). Treat the scores as one person's judgement, not a
measurement.

**What is scored:** one LLM-generated plan and risk register per environment, from the
consistency run (`scripts/consistency_check.py`). The generated projects are in
`docs/generated/`; open them in the app by loading the JSON, or read the task and risk lists
directly. Score the run named in the table, not the best of several.

**Scale (per criterion):** 0 = poor or missing, 1 = acceptable with clear gaps, 2 = good.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Scope coverage | Major parts of the brief have no task | Most of the brief is covered, some parts missing | Every part of the brief appears as tasks |
| Dependency logic | Several dependencies are wrong or missing | Mostly sensible, a few odd links | Order matches how the work would really go |
| Estimate plausibility | Many estimates are unrealistic | Some are off by a clear margin | Estimates and their ranges look realistic |
| Parallelism | Everything is in one long chain | Some parallel work | Independent work runs in parallel |
| Risk specificity | Generic risks that fit any project | Mix of generic and specific | Risks name this project's real hazards |
| Risk-category coverage | One or two categories | Three or four categories | Five or six categories, none forced |
| Response actionability | Responses are vague ("monitor") | Some concrete responses | Each response says who does what |
| Role fit | Tasks are given to the wrong roles | A few mismatched roles | Every task has a fitting role |

## Scores

Fill in the scores after reading each plan (0-2). The run column says which generated file to
read.

| Criterion | Software | Event | Construction |
|---|---|---|---|
| Run scored | `software_run1.json` | `event_run1.json` | `construction_run1.json` |
| Scope coverage | | | |
| Dependency logic | | | |
| Estimate plausibility | | | |
| Parallelism | | | |
| Risk specificity | | | |
| Risk-category coverage | | | |
| Response actionability | | | |
| Role fit | | | |
| **Total (max 16)** | | | |

## Notes

Write one or two lines per environment on what the rating reflects (for example "estimates for
the sponsor tasks look too short") so the report can cite the reason.

- Software:
- Event:
- Construction:

## Limits

Single rater, three plans, no inter-rater check, and the rater also built the tool. The scores
show whether the output is usable as a first draft, not that it is correct.
