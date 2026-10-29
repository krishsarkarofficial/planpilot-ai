import hashlib

import streamlit as st

from planpilot import viz
from planpilot.config import DEFAULT_SEED, PROGRESS_DEFAULTS, RAG_AMBER, RAG_GREEN, WEEK_DAYS
from planpilot.engine.evm import (
    default_as_of_week,
    evm_series,
    planned_curve,
    planned_weeks,
    simulate_progress,
    status_at,
    task_progress,
)
from planpilot.llm.chains import status_chain
from planpilot.llm.client import LLMError
from planpilot.status import lakh, status_facts, template_status
from planpilot.ui import current_seed, is_offline, llm_client, sidebar

st.set_page_config(page_title="Execution · PlanPilot AI", layout="wide")
project = sidebar()

st.title("Execution: earned value")
if project is None:
    st.info("Load a demo project from the sidebar, or generate one on Home.")
    st.stop()

st.subheader(project.name)
defaults = PROGRESS_DEFAULTS[project.environment]
seed = current_seed()
c1, c2, c3 = st.columns(3)
week = c1.slider(
    "Status date (end of week)", 1, planned_weeks(project), default_as_of_week(project)
)
slip = c2.slider(
    "Schedule slip (× elapsed time)",
    0.8,
    1.6,
    defaults["slip"],
    0.01,
    help="Each task takes most-likely duration × slip × noise; delays push successors back.",
)
overrun = c3.slider(
    "Cost overrun (× spend)", 0.8, 1.5, defaults["cost_overrun"], 0.01, help="Spend per % done."
)
progress = simulate_progress(project, week, slip, overrun, seed)
is_demo_progress = (week, slip, overrun, seed) == (
    default_as_of_week(project),
    defaults["slip"],
    defaults["cost_overrun"],
    DEFAULT_SEED,
)
st.caption(
    f"Progress is simulated from the current plan (seed {seed})."
    + (
        f" These are the demo settings saved in `data/sample/{project.environment}_progress.csv`."
        if is_demo_progress
        else ""
    )
)

s = status_at(project, progress)
series = evm_series(project, progress)
badge = {
    "green": ("green", ":material/check_circle:"),
    "amber": ("orange", ":material/warning:"),
    "red": ("red", ":material/error:"),
}
color, icon = badge[s.rag]
st.badge(f"Status {s.rag.upper()} at the end of week {s.week}", icon=icon, color=color)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Budget at completion (BAC)", lakh(s.bac))
c2.metric("Planned value (PV)", lakh(s.pv))
c3.metric("Earned value (EV)", lakh(s.ev))
c4.metric("Actual cost (AC)", lakh(s.ac))
c1, c2, c3, c4 = st.columns(4)
c1.metric("SPI (EV / PV)", f"{s.spi:.2f}")
c2.metric("CPI (EV / AC)", f"{s.cpi:.2f}")
c3.metric("Estimate at completion (EAC)", lakh(s.eac))
c4.metric("Variance at completion (VAC)", lakh(s.vac))

left, right = st.columns([1, 2])
with left:
    st.plotly_chart(viz.index_gauge(s.spi, "SPI", RAG_GREEN, RAG_AMBER), width="stretch")
    st.plotly_chart(viz.index_gauge(s.cpi, "CPI", RAG_GREEN, RAG_AMBER), width="stretch")
with right:
    st.markdown("#### PV, EV and AC")
    st.plotly_chart(viz.evm_curves(planned_curve(project), series, s.bac), width="stretch")

st.markdown("#### Status report")
facts = status_facts(project, progress)
key = hashlib.sha256(facts.encode("utf-8")).hexdigest()
if st.button("Write the report with the LLM", disabled=is_offline()):
    with st.spinner("Writing the status report and checking its figures…"):
        try:
            st.session_state["status_report"] = {
                "key": key,
                "report": status_chain(llm_client(), project, progress),
                "error": None,
            }
        except LLMError as e:
            st.session_state["status_report"] = {"key": key, "report": None, "error": str(e)}
saved = st.session_state.get("status_report")
if saved and saved["key"] == key and saved["error"]:
    st.error(f"Could not write a report that uses only the given figures: {saved['error']}")
if saved and saved["key"] == key and saved["report"] is not None:
    report = saved["report"]
    st.caption("Narrated by the LLM from the figures below; every number was checked against them.")
else:
    report = template_status(project, progress)
    st.caption("Written by code from a template. The LLM button narrates the same figures.")
with st.container(border=True):
    st.markdown(f"**{report.headline}**")
    st.markdown(report.summary)
    st.markdown(f"**Schedule.** {report.schedule}")
    st.markdown(f"**Cost.** {report.cost}")
    left, right = st.columns(2)
    left.markdown("**Issues**\n" + "\n".join(f"- {x}" for x in report.issues))
    right.markdown("**Actions**\n" + "\n".join(f"- {x}" for x in report.actions))
with st.expander("Facts given to the LLM"):
    st.code(facts, language=None)

st.markdown("#### Tasks at the status date")
st.dataframe(
    task_progress(project, progress),
    hide_index=True,
    width="stretch",
    column_config={
        "id": "ID",
        "name": "Task",
        "role": "Role",
        "critical": st.column_config.CheckboxColumn("Critical"),
        "planned_pct": st.column_config.ProgressColumn("Planned", format="percent"),
        "actual_pct": st.column_config.ProgressColumn("Actual", format="percent"),
        "pv": st.column_config.NumberColumn("PV (₹)", format="%.0f"),
        "ev": st.column_config.NumberColumn("EV (₹)", format="%.0f"),
        "ac": st.column_config.NumberColumn("AC (₹)", format="%.0f"),
        "sv": st.column_config.NumberColumn("SV = EV − PV (₹)", format="%.0f"),
    },
)

with st.expander("How this was computed"):
    st.markdown(
        f"""
- **Budget:** each task's budget is its most-likely duration × the daily rate of its role;
  BAC is their sum ({lakh(s.bac)}). It has no risk allowance, so it is lower than the Monte
  Carlo cost forecast.
- **Planned value:** a task is planned to progress linearly from its CPM early start to its
  early finish. PV at week *w* (working day {WEEK_DAYS}·*w*) = Σ planned % × budget.
- **Progress:** simulated from the current plan, so it works for any generated project. Each
  task's actual duration is most likely × slip × noise (±15%); a CPM pass on those durations
  pushes successors back. Spend = actual % × budget × overrun × noise (±5%). Slip stretches
  elapsed time only, so SPI and CPI can be set independently.
- **Indices:** EV = Σ actual % × budget; AC = Σ actual cost; SPI = EV / PV; CPI = EV / AC;
  EAC = BAC / CPI; VAC = BAC − EAC.
- **RAG:** green if both SPI and CPI ≥ {RAG_GREEN}, amber if the lower is ≥ {RAG_AMBER},
  otherwise red.
- **Status report:** code computes every figure in the fact sheet above. The LLM only narrates
  it; any number in its report that is not in the fact sheet, or an unknown task or risk id,
  is sent back as an error and retried (up to 3 attempts).
"""
    )
