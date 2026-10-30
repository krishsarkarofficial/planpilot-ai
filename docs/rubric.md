# Plan quality rubric

There is no ground truth for what a good project plan is, so plan quality is judged against a
short rubric by a **single rater**.

**Who scored this.** The scores below were given by **Claude (an LLM, Claude Sonnet 5.5)** at the
author's request, from reading each generated project against its brief. They were **not** given by
a human project manager. Claude also helped build the tool, the plans came from a different LLM
(`openai/gpt-oss-120b`), and the rating was not blind. Treat the scores as a documented first-pass
judgement with its evidence, not as a measurement; the author should read the plans and override
any score they disagree with.

**What is scored:** one LLM-generated plan and risk register per environment, from the consistency
run (`scripts/consistency_check.py`): run 1 of each, not the best of several. The generated
projects are in `docs/generated/`.

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

| Criterion | Software | Event | Construction |
|---|---|---|---|
| Run scored | `software_run1.json` | `event_run1.json` | `construction_run1.json` |
| Scope coverage | 2 | 1 | 2 |
| Dependency logic | 1 | 1 | 1 |
| Estimate plausibility | 1 | 1 | 1 |
| Parallelism | 2 | 2 | 2 |
| Risk specificity | 1 | 2 | 2 |
| Risk-category coverage | 2 | 2 | 2 |
| Response actionability | 2 | 2 | 2 |
| Role fit | 2 | 2 | 1 |
| **Total (max 16)** | **13** | **13** | **13** |

## Evidence

**Software** (19 tasks, 9 risks, CPM 37 working days, 11-week brief).
- Scope 2: profiles, company posting, application workflow, email notifications, admin
  dashboard, migration, testing and go-live all appear (T09-T19).
- Dependencies 1: migration (T12) depends only on the project plan (T04), so it can start before the
  database schema (T06) exists; the admin dashboard (T15) does not depend on the application
  workflow (T11) whose data it reports.
- Estimates 1: modules take 5-6 days each, UAT 3 days and the kickoff meeting 1 day; the 37-day CPM
  is well under the roughly 57 working days the brief allows. Aggressive, ranges are narrow.
- Parallelism 2: wireframes, schema, migration and environment setup run alongside each other
  (slack up to 11 days on T12).
- Risk specificity 1: R07 (migration character errors) fits the spreadsheet migration, but R01, R03,
  R04 and R08 fit almost any software project. R03 calls the developer a "single-person bottleneck"
  although the team has three developers. Nothing on exams, SSO or mail limits.
- Categories 2: all six categories appear.
- Responses 2: concrete (pilot migration on a sample, access request in week 1, change-control
  process). The owner is in the `owner_role` field, not in the text.
- Role fit 2: roles match the work (schema to developer, templates to designer, UAT to tester).

**Event** (18 tasks, 9 risks, CPM 30 working days, 9-week brief).
- Scope 1: the brief asks for security, a robotics competition, a hackathon and a concert; there are
  no tasks for security or medical cover and none that builds the robotics or hackathon programme
  (only a general schedule task, T15).
- Dependencies 1: the social campaign (T10) does not wait for the registration platform (T08), and
  the sponsorship proposal (T05) is made before the branding assets (T07).
- Estimates 1: negotiating sponsors takes 4 days, launching a social campaign 5 days and the
  two-day event 7 days, which are short for real work.
- Parallelism 2: volunteers, workshops, branding and registration branch off the kickoff (slack up
  to 10 days).
- Risk specificity 2: venue permission, sponsor shortfall, volunteer drop-out, rain on food stalls
  and AV failure fit a college fest; scope creep and branding delay are generic.
- Categories 2: all six appear.
- Responses 2: concrete (recruit 30% more volunteers, test equipment 48 hours before, backup sponsors).
- Role fit 2: sensible; sponsor outreach (T04) sits with finance, which is debatable but defensible.

**Construction** (16 tasks, 9 risks, CPM 30 working days, 14-week brief).
- Scope 2: permit, strip-out, partitions, wiring, plumbing, ducting, flooring, ceiling and lighting,
  benches, fire inspection and handover are all present.
- Dependencies 1: the site survey (T03) comes after the permit and the fire plan approval, when it
  would normally come first; flooring (T07) runs in parallel with the dirty electrical and plumbing
  work.
- Estimates 1: a building permit in 5 working days and fire plan approval in 3 are unrealistic (the
  plan's own R01 is a permit backlog); the on-site tasks look plausible.
- Parallelism 2: five trades start together after demolition (T06-T10).
- Risk specificity 2: asbestos in old fittings, hidden structural support, timber stud supply, LED
  circuit errors and cold-weather curing are specific to this job.
- Categories 2: all six appear.
- Responses 2: concrete (asbestos survey before demolition, penalty clause plus a second supplier).
- Role fit 1: fume-hood ducting (T10) goes to a carpenter, and the fire safety plan (T02) to the
  supervisor; the preset has no HVAC or fire-safety role.

## Limits

One rater that is an LLM, three plans (one run each), no inter-rater check, not blind, and the
rater helped build the tool. All three plans total 13, which may reflect a coarse 0-2 scale and the
rater's leniency as much as the plans. The scores show that the output is usable as a first draft with
known gaps (estimates, a few dependencies); they do not show that the plans are correct.
