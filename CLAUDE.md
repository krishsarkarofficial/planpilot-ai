# CLAUDE.md

## Project
PlanPilot AI: an LLM project copilot. A project brief goes in; a WBS, CPM schedule, risk register, Monte Carlo forecast, earned-value status report and decision memo come out. Solo university project for the theme "How AI can support project planning, execution, risk management, and decision-making across real project environments". **Read PLAN.md first**; it is the source of truth for scope, specs, build order and the schedule.

## Stack
Python 3.11, Streamlit, Plotly, NumPy, pandas, Pydantic v2, `openai` SDK (pointed at Groq or Gemini OpenAI-compatible endpoints), pytest, ruff. Developer machine is **Windows (PowerShell)**.

## Commands
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/Home.py
pytest -q
ruff check . ; ruff format .
python scripts/make_demo_data.py
```

## Architecture rules (do not break these)
1. **The LLM proposes, the code verifies.** Never ask an LLM to calculate a metric. All numbers come from `planpilot/engine/`.
2. `planpilot/engine/` is pure Python: no LLM calls, no Streamlit, no network. Functions take explicit inputs and a seed, and are deterministic.
3. Every LLM output is parsed into a Pydantic model, then passed through `check_plan`/semantic checks. On errors retry up to 3 times with the error appended to the prompt. Warnings are shown to the user, not retried.
4. Every LLM call goes through `planpilot/llm/client.py`. The cache is for dev speed only. **The offline demo uses frozen projects in `data/sample/`, not cache hits.** `use_cache=False` must truly bypass the cache.
5. **LLM calls happen only inside an explicit button click**, with results stored in `st.session_state`. Streamlit reruns on every interaction; never call the LLM at module level or in a page body.
6. Prompts live in `prompts/*.md`, each with a few-shot example. No prompt strings inline in code.
7. Streamlit pages contain UI only; logic lives in `planpilot/`.
8. Use the same seed for all options in a comparison (common random numbers).
9. Never commit `.env`, API keys, or third-party datasets. Synthetic data only (plus the optional real case, non-sensitive).

## Build order
Engines first on a frozen sample project (P1-P4), LLM layer after (P5-P6). Do not start an LLM phase until the engine phases pass their tests.

## Conventions
- Type hints everywhere; Pydantic models for structured data; small functions.
- Durations are working days; dates via `numpy.busday_offset`.
- Charts live in `planpilot/viz.py` and return Plotly figures.
- Triangular distribution mean is (o + m + p)/3. Do not write tests that assume the PERT mean (o + 4m + p)/6.
- **Windows:** open files with `encoding="utf-8"`; use `pathlib`; no hard-coded backslashes.
- Free-tier LLM limits are tight: cache in dev, keep calls per page small, never loop over API calls.

## How to work
- Follow the phases in PLAN.md in order. Tick the checkbox in PLAN.md when a phase's exit criterion is met, then commit with a clear message (`P2: schedule engine + Gantt`) and push.
- Keep each phase in a focused session; commit before starting the next so work is never lost.
- Stop at the MVP checkpoint (after P6) and report status before continuing. Feature freeze is at 16:30 Friday.
- Save screenshots of working pages to `docs/images/` with numbered names matching PLAN.md section 14.
- If something in PLAN.md is ambiguous or blocked (for example API quota), pick the simplest option, add a "Decisions" line to PLAN.md, and keep going.
- Do not add features outside PLAN.md. The cut list in PLAN.md section 10 applies.
