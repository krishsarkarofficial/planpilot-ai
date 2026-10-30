import streamlit as st

from planpilot import viz
from planpilot.engine.schedule import check_plan, cpm, deadline_days, schedule_frame
from planpilot.ui import require_project, sidebar

st.set_page_config(
    page_icon=":material/calendar_month:", page_title="Plan · PlanPilot AI", layout="wide"
)
project = sidebar()

st.title("Plan")
project = require_project(project)

sched = cpm(project)
df = schedule_frame(project, sched)
errors, warnings = check_plan(project)

st.subheader(project.name)
c1, c2, c3, c4 = st.columns(4)
c1.metric("CPM duration (working days)", f"{sched.duration:g}")
c2.metric("Planned finish", df["finish"].max().strftime("%d %b %Y"))
c3.metric("Deadline", project.deadline.strftime("%d %b %Y"))
c4.metric("Tasks on critical path", f"{len(sched.critical)} of {len(project.tasks)}")

st.markdown("#### Plan checks")
if not errors and not warnings:
    st.success("All plan checks passed.")
for e in errors:
    st.error(e, icon="⛔")
for w in warnings:
    st.warning(w, icon="⚠️")

st.markdown("#### Gantt chart")
st.plotly_chart(viz.gantt(df, project.deadline), width="stretch")

st.markdown("#### Work breakdown")
st.dataframe(
    df.drop(columns=["es", "ef"]),
    hide_index=True,
    width="stretch",
    column_config={
        "id": "ID",
        "name": "Task",
        "phase": "Phase",
        "role": "Role",
        "o": st.column_config.NumberColumn("Optimistic", format="%g"),
        "m": st.column_config.NumberColumn("Most likely", format="%g"),
        "p": st.column_config.NumberColumn("Pessimistic", format="%g"),
        "depends_on": "Depends on",
        "slack": st.column_config.NumberColumn("Slack (days)", format="%g"),
        "critical": "Critical",
        "start": st.column_config.DateColumn("Start", format="DD MMM YYYY"),
        "finish": st.column_config.DateColumn("Finish", format="DD MMM YYYY"),
    },
)

with st.expander("How this was computed"):
    st.markdown(
        f"""
- **Schedule:** critical path method on the *most-likely* durations. A forward pass gives each
  task's earliest start and finish; a backward pass from the project end gives the latest
  start and finish. Slack = latest start − earliest start. Tasks with zero slack form the
  critical path.
- **Dates:** working days (Mon–Fri) counted from the start date
  {project.start_date:%d %b %Y} with `numpy.busday_offset`.
- **Plan checks:** structural problems (cycles, unknown ids or roles) are rejected when the
  plan is loaded. The checks above flag plan-quality issues: task count (12–30), phases
  with fewer than two tasks, dead-end tasks, a single start task, no parallel work,
  CPM duration outside 0.5×–2× of the {deadline_days(project)}-working-day
  timeframe, and fewer than three risk categories.
- No LLM is involved in any number on this page.
"""
    )
