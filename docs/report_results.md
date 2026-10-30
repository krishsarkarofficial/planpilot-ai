# Result / Output: draft

Draft of the report's Result section, written from the committed demo projects and the engines
(seed 42, 10,000 runs). Every number below was read from the code, not typed from memory. Edit the
wording freely; keep the numbers tied to `data/sample/` and the seed.

**Read this first (for the report's framing).** The three demo projects are synthetic. Their
deadlines were set at about the baseline P65 so that the probability of meeting the deadline is
neither 0% nor 100%; the 65-69% figures are therefore a design choice, not a finding. The earned-value
progress is simulated from the plan with injected slip, so SPI 0.82 and CPI 0.90 are inputs, not
observations of a real project.

## Figures

The figures use the software demo (College Placement Portal, 19 tasks, 9 risks) unless stated.

**Figure 1. Home page with the brief and the environment preset** (`docs/images/01_home_brief_generate.jpg`).
The user picks an environment (software, event or construction), enters a brief, a start date and a
deadline, and clicks Generate. The LLM is called only on that click.

**Figure 2. WBS table and plan checks** (`docs/images/02_wbs_plan_checks.jpg`).
The LLM-drafted work breakdown is validated for ids, dependencies, cycles and roles, then checked for
plausibility. The software demo raises one warning: only one start task (T01), so work cannot begin
in parallel. Warnings are shown, errors are sent back to the LLM.

**Figure 3. Gantt chart with the critical path** (`docs/images/03_gantt_critical_path.jpg`).
The most-likely schedule takes 43 working days. The deadline is 57 working days (19 Jan 2027), so
the deterministic plan looks comfortable. The simulation shows why that is misleading (Figure 5).

**Figure 4. Risk register and 5x5 heatmap** (`docs/images/04_risk_register_heatmap.jpg`).
Code scores each risk as probability level x impact level. The top three, each scoring 9, are R06
integration defects (p 0.45, 4 days), R01 messy legacy data (0.40, 4 days) and R04 UAT clashing with
exams (0.35, 4 days). Adding the register moves the P80 finish from 49.1 to 59.0 working days.

**Figure 5. Monte Carlo histogram with P50/P80 and S-curve** (`docs/images/05_monte_carlo_histogram_scurve.jpg`).
P50 54.6, P80 59.0 and P90 61.5 working days against a 43-day most-likely plan; probability of
meeting the 57-day deadline 68%. Expected cost P50 / P80 / P90 is ₹3.74 / 3.97 / 4.10 lakh.
Three-point estimates and risk events push the realistic finish well beyond the single-point plan.

**Figure 6. Tornado and criticality index** (`docs/images/06_tornado_criticality.jpg`).
T09 (application tracking workflow) correlates most with the finish date (0.49), then T15 integration
testing (0.44) and T16 user acceptance testing (0.39). T09 is on the critical path in 99% of runs;
T12 (admin dashboard) in 85%. Several tasks share the critical path across runs, so a single
deterministic critical path understates where the schedule is fragile.

**Figure 7. Earned-value dashboard and RAG status report** (`docs/images/07_evm_dashboard_rag_report.jpg`).
At the end of week 5: BAC ₹3.04 lakh, PV ₹2.19 lakh, EV ₹1.79 lakh, AC ₹1.99 lakh, so SPI 0.82 and
CPI 0.90, EAC ₹3.38 lakh (VAC -₹0.33 lakh), status RED. The report names T09 (26% done against 100%
planned, on the critical path) and T10 as the main issues. Code computed every figure; the LLM only
narrates, and a figure outside the fact sheet is rejected and retried.

**Figure 8. Decision comparison, weight scenarios and memo** (`docs/images/08_decision_comparison_memo.jpg`).
Three options are applied to the plan and re-simulated with the same random draws, alongside the
baseline (Table 2). Under balanced weights "Add two developers" ranks first, but the winner changes to
"Mitigate risks and add a buffer" under cost-first weights, so the memo reports the recommendation
as weight-dependent.

**Figure 9. The same pipeline on the other two environments** (`docs/images/09a_event_simulation.jpg`, `09b_construction_simulation.jpg`).
Event demo (TechNova): P50 44.6, P80 48.6 working days, 69% on time; the sponsorship task T03
correlates most with the finish (0.72). Construction demo (lab renovation): P50 68.7, P80 73.8, 65%
on time; the building permit T04 correlates most (0.64). Only the roles, rates and plan differ; no
code changed between environments.

**Figure 10. pytest and CI passing** (to capture: terminal `pytest -q` showing 119 passed, and the
green CI run on GitHub).

## Tables

**Table 1. Consistency of the LLM** (3 runs per brief, cache bypassed, temperature 0.7, Groq
`openai/gpt-oss-120b`; 9 of 9 runs valid; source `docs/consistency.csv`).

| Environment | Tasks | Total most-likely days | Critical-path days | Risks |
|---|---|---|---|---|
| Software | 18-22 | 68-87 | 37-46 | 9-10 |
| Event | 18-20 | 70-93 | 30-50 | 9-10 |
| Construction | 16-18 | 64-75 | 30-53 | 9-10 |

Task and risk counts are stable. The critical-path length is not: the same brief gave plans that
differ by up to 23 working days (construction). Generated plans are drafts for a person to review.

**Table 2. Decision options, software demo** (deadline 19 Jan 2027, 57 working days).

| Alternative | P80 finish (working days) | P(meet deadline) | Expected cost (₹ lakh) | Spread P90-P50 |
|---|---|---|---|---|
| Baseline (no change) | 59.0 | 68% | 3.76 | 6.9 |
| Add two developers | 52.4 | 96% | 6.03 | 6.6 |
| Drop the admin dashboard | 56.2 | 84% | 3.48 | 6.8 |
| Mitigate risks and add a buffer (+3 days) | 56.6 | 93% | 3.99 | 6.4 |

Winner by weight scenario: balanced and schedule-first "Add two developers"; cost-first "Mitigate
risks and add a buffer". The scores come from min-max scaling over four alternatives, which
exaggerates small gaps (balanced: 0.70 for "Add two developers" against 0.69 for the
mitigation option), so read the raw values above rather than the scores alone.

**Table 3. Decision winners on all three demos.**

| Demo | Balanced | Schedule-first | Cost-first | Stable? |
|---|---|---|---|---|
| Software | Add two developers | Add two developers | Mitigate risks and add a buffer | No |
| Event | Drop the robotics arena | Drop the robotics arena | Drop the robotics arena | Yes |
| Construction | Fast-track permit and pre-inspection | Add two masons | Fast-track permit and pre-inspection | No |

The event result comes from a cut-scope option whose value is not modelled, so it looks cheap and
fast by construction. A person would need to decide whether the robotics arena is dispensable.

**Table 4. Plan quality rubric** (0-2 per criterion, max 16; one generated plan per environment;
evidence for every score is in `docs/rubric.md`). The rater was an LLM (Claude), not a human, and it
helped build the tool; the rating was not blind. Present it as a documented first-pass judgement.

| Criterion | Software | Event | Construction |
|---|---|---|---|
| Scope coverage | 2 | 1 | 2 |
| Dependency logic | 1 | 1 | 1 |
| Estimate plausibility | 1 | 1 | 1 |
| Parallelism | 2 | 2 | 2 |
| Risk specificity | 1 | 2 | 2 |
| Risk-category coverage | 2 | 2 | 2 |
| Response actionability | 2 | 2 | 2 |
| Role fit | 2 | 2 | 1 |
| **Total** | **13** | **13** | **13** |

The recurring gaps are short estimates (for example a building permit in 5 working days) and a few
wrong dependencies (for example a site survey after the permit). Identical totals may reflect the
coarse 0-2 scale as much as the plans.

## Stating the limits in the report

- Plan quality has no ground truth; the checks catch structure and plausibility only.
- The cost model assumes one person-equivalent per task. Extending a deadline costs nothing in the
  model, and the value of cut scope is not modelled.
- The demo projects and progress data are synthetic.
- Estimates come from the LLM and vary between runs (Table 1).
- The rubric was scored by an LLM, not a human (Table 4).
