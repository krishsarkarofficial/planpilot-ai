# PlanPilot AI: an LLM project copilot that proposes and code that verifies

*Draft of the report text (everything except the Result section, which is in
`docs/report_results.md`). Written for Krish Sarkar to edit. Check every reference against the
original source before submitting; I wrote them from memory of well-known works and have not
re-opened them.*

**Theme:** How AI can support project planning, execution, risk management, and decision-making
across real project environments.

## Objective

The project builds PlanPilot AI, a working prototype that takes a short project brief and returns a
work breakdown structure, a critical-path schedule, a risk register, a Monte Carlo forecast, an
earned-value status report and a decision memo. It has four goals, one for each part of the theme:

1. **Planning.** Turn a brief into a validated work breakdown with three-point estimates and
   dependencies, schedule it with the critical path method, and check the plan for structural and
   plausibility problems.
2. **Execution.** Track progress with earned value (PV, EV, AC, SPI, CPI, EAC) and report the status
   as red, amber or green with a short written report.
3. **Risk management.** Draft a risk register, score it on a probability-impact matrix, and
   simulate the finish date and cost to give P50, P80 and P90 values, the chance of meeting the
   deadline and the tasks that drive the result.
4. **Decision-making.** Compare options (add people, cut scope, mitigate risks, extend the deadline)
   by re-simulating each one, rank them under three sets of weights, and write a decision memo.

A fifth, cross-cutting aim is to show that the same pipeline works in different project
environments. The prototype ships three: software, event and construction.

## Introduction

### The problem

Project plans are usually built from single-point estimates, and single-point estimates are almost
always too optimistic. Behavioural research on the planning fallacy shows that people underestimate
how long their own tasks will take, even when they know similar tasks ran late before (Kahneman and
Tversky, 1979; Buehler, Griffin and Ross, 1994). Construction and infrastructure projects show the
same pattern at large scale (Flyvbjerg, Bruzelius and Rothengatter, 2003). A schedule that shows one
finish date hides the spread of likely outcomes, which Savage (2012) calls the flaw of averages.
Estimates are least certain early in a project, when plans are made (Boehm, 1981). Planning,
risk analysis and tracking are also separate chores, done in separate tools, so the risk
register and the schedule rarely talk to each other.

### What large language models add, and where they fail

A large language model (LLM) can read a plain-language brief and draft a plausible task list and
risk register in seconds, and given a worked example in the prompt it can follow a required output
format (Brown et al., 2020). That removes a blank-page problem for small teams. But LLMs are unreliable in exactly the places a
project plan needs rigour: they can invent facts (Ji et al., 2023), they do not reliably do
arithmetic, and the same prompt can return different plans. This was measured in the project: three
runs of the same brief gave critical paths that differed by up to 23 working days (Result, Table 1).

### Design principle: the LLM proposes, the code verifies

PlanPilot AI therefore splits the work. The LLM does what it is good at: drafting tasks, estimates,
risks and prose. Deterministic, seeded, tested Python does everything else:

- Every LLM output is parsed into a typed model (Pydantic), checked for structure (known task ids,
  roles and dependencies, no cycles) and for plausibility (task counts, phases, parallel work). Errors
  are sent back to the LLM with the error text, up to three attempts.
- No metric is ever calculated by the LLM. Schedule, simulation, earned-value and decision figures
  come from the engines. For the status report and the decision memo, code computes a fact sheet and
  the LLM may only narrate it: a number that is not in the fact sheet, an unknown task or risk id, or
  a memo recommendation that differs from the code's ranking is rejected and retried.
- LLM calls happen only when the user clicks a button, and the app works offline on three frozen,
  validated demo projects with no API key.

### Methods used

- **Critical path method (CPM)** finds the longest chain of dependent tasks and the slack of every
  other task (Kelley and Walker, 1959).
- **Three-point estimates and Monte Carlo simulation.** Each task has an optimistic, most-likely and
  pessimistic duration. The simulation samples a triangular distribution (mean (o + m + p) / 3, not
  the PERT weighting (o + 4m + p) / 6 of Malcolm et al., 1959) and adds discrete risk events. It runs
  10,000 times with a fixed seed. Each task and risk has its own random stream, so options compared
  later use the same random draws (common random numbers) and differences come from the option.
- **Risk scoring** uses a 5x5 probability-impact matrix. Such qualitative matrices have known
  weaknesses (Hubbard, 2009), so here the matrix is paired with a simulation that uses the same
  probabilities and impacts.
- **Earned value management** computes planned value, earned value, actual cost, SPI, CPI and the
  estimate at completion, with a red-amber-green status (Fleming and Koppelman, 2010; PMI, 2021).
- **Option analysis** applies each option to the plan, re-simulates it, normalises four criteria
  (P80 finish, probability of meeting the deadline, expected cost, spread) and scores them under
  balanced, schedule-first and cost-first weights. Adding people uses an assumed efficiency below one
  to reflect coordination overhead (Brooks, 1975).

### Scope

PlanPilot AI is a decision-support prototype, not a project management suite. It does not replace a
project manager, integrate with scheduling tools, or learn from past projects. The demo projects are
synthetic: a college placement portal (software), a college tech fest (event) and a campus lab
renovation (construction). The earned-value progress is simulated from the plan, not taken from a
real project. These choices are deliberate, so that the whole pipeline can be shown, tested and
reproduced without private data.

### Architecture

The app is a Streamlit multipage application over a Python package. Pages contain only user
interface code. LLM chains (plan, risk, status, memo) call one client that talks to an
OpenAI-compatible endpoint (Groq first, Gemini as a fallback). Their validated output feeds the
engines (schedule, risk scoring, Monte Carlo, earned value, decision), which are pure Python with no
network access. Plotly figures are built in one module. The architecture diagram is in the README.

## Result / Output

See `docs/report_results.md` (figures 1-10 and tables 1-4).

## Conclusion

**What worked.**
- The split between proposing and verifying held up. In 9 of 9 consistency runs the LLM produced a
  valid plan and risk register within the retry limit, and the code-computed figures were
  reproducible: the same seed gave identical results, and 119 automated tests pass in CI.
- One pipeline served three very different environments with only the roles, rates and plan changing.
- Simulation exposed what the single-point plan hid. For the software demo the most-likely plan takes
  43 working days and looks comfortable against a 57-day deadline, while the simulation gives a P80
  of 59.0 days and a 68% chance of meeting the deadline.
- The decision module shows when a recommendation is fragile. For the software and construction demos
  the best option changes with the weights, and the memo says so instead of hiding it.

**Limitations.**
- There is no ground truth for plan quality. The checks catch structural and plausibility problems
  only, and the rubric score (13 of 16 for each plan) was given by an LLM, not a human, so it is a
  documented first-pass judgement rather than a measurement.
- LLM plans vary between runs, and estimates tend to be short (for example a building permit in
  5 working days). A generated plan is a draft to be reviewed.
- The cost model assumes one person-equivalent per task. Extending a deadline costs nothing and the
  value of cut scope is not modelled, so those options look better than they would in practice.
- The demo projects and the progress data are synthetic, and the deadlines were calibrated to about
  the baseline P65, so the 65-69% on-time probabilities are a design choice, not a finding.
- The LLM cannot pin a date inside a plan (for example "the fest is in late January").
- Free-tier LLM rate limits cost 4 of the first 9 consistency runs until the script was made to wait
  and retry.

**Human in the loop.** The tool is built so that a person stays in charge. Warnings are shown rather
than hidden, the memo recommends only the option the code ranked first, and the text states when the
winner depends on the weights. The decision is a person's.

**Future work.**
- Accept real weekly progress (CSV) instead of simulating it, and test the tool on a real project
  with planned and actual dates.
- Model the cost of extending a deadline and the value of scope, and let users set their own weights.
- Score plan quality with more than one human rater and more than one run per environment.
- Wrap the engines in a service (for example FastAPI) so other tools can use them.

## References

*Verify each against the source before submitting.*

1. Boehm, B. W. (1981). *Software Engineering Economics*. Prentice-Hall.
2. Brooks, F. P. (1975). *The Mythical Man-Month: Essays on Software Engineering*. Addison-Wesley.
3. Brown, T. B., et al. (2020). Language models are few-shot learners. *Advances in Neural
   Information Processing Systems*, 33.
4. Buehler, R., Griffin, D. and Ross, M. (1994). Exploring the "planning fallacy": Why people
   underestimate their task completion times. *Journal of Personality and Social Psychology*, 67(3),
   366-381.
5. Fleming, Q. W. and Koppelman, J. M. (2010). *Earned Value Project Management* (4th ed.). Project
   Management Institute.
6. Flyvbjerg, B., Bruzelius, N. and Rothengatter, W. (2003). *Megaprojects and Risk: An Anatomy of
   Ambition*. Cambridge University Press.
7. Hubbard, D. W. (2009). *The Failure of Risk Management: Why It's Broken and How to Fix It*. Wiley.
8. Ji, Z., et al. (2023). Survey of hallucination in natural language generation. *ACM Computing
   Surveys*, 55(12), Article 248.
9. Kahneman, D. and Tversky, A. (1979). Intuitive prediction: Biases and corrective procedures.
   *TIMS Studies in Management Science*, 12, 313-327.
10. Kelley, J. E. and Walker, M. R. (1959). Critical-path planning and scheduling. *Proceedings of
    the Eastern Joint Computer Conference*, 160-173.
11. Malcolm, D. G., Roseboom, J. H., Clark, C. E. and Fazar, W. (1959). Application of a technique
    for research and development program evaluation. *Operations Research*, 7(5), 646-669.
12. Project Management Institute (2021). *A Guide to the Project Management Body of Knowledge
    (PMBOK Guide)* (7th ed.). PMI.
13. Savage, S. L. (2012). *The Flaw of Averages: Why We Underestimate Risk in the Face of
    Uncertainty*. Wiley.
