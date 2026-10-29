import streamlit as st

from planpilot import viz
from planpilot.config import N_ITERATIONS
from planpilot.engine.schedule import cpm, finish_date
from planpilot.ui import current_seed, run_simulation, sidebar

st.set_page_config(page_title="Simulation · PlanPilot AI", layout="wide")
project = sidebar()

st.title("Monte Carlo simulation")
if project is None:
    st.info("Load a demo project from the sidebar.")
    st.stop()

seed = current_seed()
res = run_simulation(project, seed)
names = {t.id: t.name for t in project.tasks}

st.subheader(project.name)
st.caption(
    f"{N_ITERATIONS:,} runs · seed {seed} · "
    f"CPM (most-likely) duration {cpm(project).duration:g} working days"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "P(meet deadline)", f"{res.prob_on_time:.0%}", help=f"Deadline {project.deadline:%d %b %Y}"
)
for col, q in ((c2, 50), (c3, 80), (c4, 90)):
    d = res.percentile(q)
    col.metric(f"P{q} finish", f"{finish_date(project, d):%d %b %Y}", help=f"{d:.1f} working days")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Deadline", f"{project.deadline:%d %b %Y}", help=f"{res.deadline_days} working days")
for col, q in ((c2, 50), (c3, 80), (c4, 90)):
    col.metric(f"P{q} cost", f"₹{res.percentile(q, 'cost') / 1e5:.2f} lakh")

left, right = st.columns(2)
with left:
    st.markdown("#### Duration distribution")
    st.plotly_chart(viz.duration_histogram(res), width="stretch")
with right:
    st.markdown("#### S-curve")
    st.plotly_chart(viz.s_curve(res), width="stretch")

left, right = st.columns(2)
with left:
    st.markdown("#### Tornado: what drives the finish date")
    st.plotly_chart(viz.tornado(res, names), width="stretch")
with right:
    st.markdown("#### Criticality index")
    st.plotly_chart(viz.criticality(res, names), width="stretch")

with st.expander("How this was computed"):
    st.markdown(
        f"""
- **Durations:** each run samples every task from a triangular distribution
  (optimistic, most likely, pessimistic); its mean is (o + m + p) / 3.
- **Risks:** each risk fires in a run with its probability and adds its `impact_days` to
  every affected task.
- **Schedule per run:** a forward pass gives the project duration; a backward pass gives each
  task's slack. A task is *critical* in a run when its slack is zero; the criticality index is
  the share of runs in which it is critical.
- **Cost:** sampled task days (including risk delays) × the daily rate of the task's role.
- **Tornado:** Pearson correlation between a task's sampled duration and the project duration.
- **Deadline:** on time means the project fits in the {res.deadline_days} working days up to
  and including {project.deadline:%d %b %Y}.
- **Reproducible:** seed {seed}. Each task and risk has its own random stream, so options
  compared later use the same draws (common random numbers). No LLM is involved.
"""
    )
