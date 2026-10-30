import streamlit as st

from planpilot import viz
from planpilot.engine.risks import (
    IMPACT_EDGES,
    LEVEL_LABELS,
    PROBABILITY_EDGES,
    heatmap_cells,
    register_frame,
)
from planpilot.llm.chains import risk_chain
from planpilot.llm.client import LLMError
from planpilot.ui import (
    current_seed,
    is_offline,
    llm_client,
    require_project,
    run_simulation,
    sidebar,
)

st.set_page_config(page_icon=":material/warning:", page_title="Risks · PlanPilot AI", layout="wide")
project = sidebar()

st.title("Risks")
project = require_project(project)

st.subheader(project.name)
label = "Re-draft risks with the LLM" if project.risks else "Draft risks with the LLM"
if st.button(label, type="primary" if not project.risks else "secondary", disabled=is_offline()):
    with st.spinner("Drafting the risk register and checking it…"):
        try:
            st.session_state["project"], _ = risk_chain(llm_client(), project)
            st.session_state["risk_error"] = None
            st.rerun()  # redraw the page (and button label) with the new register
        except LLMError as e:
            st.session_state["risk_error"] = str(e)
if err := st.session_state.get("risk_error"):
    st.error(f"Could not draft a valid risk register: {err}")

if not project.risks:
    st.info("This project has no risks yet. Draft them with the button above (needs the LLM).")
    st.stop()

df = register_frame(project)
seed = current_seed()
with_risks = run_simulation(project, seed)
without = run_simulation(project.model_copy(update={"risks": []}), seed)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Risks", len(project.risks))
c2.metric("Categories covered", f"{df['category'].nunique()} of 6")
p80, p80_base = with_risks.percentile(80), without.percentile(80)
c3.metric(
    "P80 duration (working days)",
    f"{p80:.1f}",
    delta=f"{p80 - p80_base:+.1f} from risks",
    delta_color="inverse",
)
c4.metric(
    "P(meet deadline)",
    f"{with_risks.prob_on_time:.0%}",
    delta=f"{(with_risks.prob_on_time - without.prob_on_time) * 100:+.0f} pts from risks",
)

left, right = st.columns(2)
with left:
    st.markdown("#### Probability × impact")
    st.plotly_chart(viz.risk_heatmap(heatmap_cells(project), LEVEL_LABELS), width="stretch")
with right:
    st.markdown("#### Register")
    st.dataframe(
        df[
            [
                "id",
                "title",
                "category",
                "probability",
                "impact_days",
                "score",
                "expected_delay",
                "affected",
                "owner",
                "strategy",
                "response",
            ]
        ],
        hide_index=True,
        width="stretch",
        height=430,
        column_config={
            "id": "ID",
            "title": "Risk",
            "category": "Category",
            "probability": st.column_config.NumberColumn("Probability", format="%.2f"),
            "impact_days": st.column_config.NumberColumn("Impact (days)", format="%g"),
            "score": st.column_config.NumberColumn("Score", help="P level × impact level"),
            "expected_delay": st.column_config.NumberColumn("Expected delay", format="%.1f"),
            "affected": "Tasks",
            "owner": "Owner",
            "strategy": "Response",
            "response": "Action",
        },
    )

with st.expander("Cause → event → effect for each risk"):
    for r in df.itertuples():
        st.markdown(f"**{r.id} {r.title}**: {r.cause} → {r.event} → {r.effect}")

with st.expander("How this was computed"):
    st.markdown(
        f"""
- **Drafted by the LLM, checked by code:** the LLM proposes risks; every risk must reference
  real task ids and an allowed owner role, and the register needs 8–12 risks, or it is retried.
- **Levels:** probability bands up to {", ".join(f"{e:g}" for e in PROBABILITY_EDGES)} and above;
  impact bands up to {", ".join(f"{e:g}" for e in IMPACT_EDGES)} working days and above.
  Score = probability level × impact level (1–25).
- **Expected delay** = probability × impact days for that risk alone.
- **Effect on the schedule:** the Monte Carlo simulation fires each risk with its probability
  and adds its delay to the affected tasks. The deltas above compare the simulation with and
  without the register (same seed {seed}). No LLM computes any of these numbers.
"""
    )
