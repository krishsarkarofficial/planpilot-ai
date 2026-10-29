from datetime import date, timedelta

import streamlit as st

from planpilot.config import PRESETS
from planpilot.llm.chains import plan_chain
from planpilot.llm.client import LLMError
from planpilot.ui import is_offline, llm_client, sidebar

st.set_page_config(page_title="PlanPilot AI", layout="wide")
project = sidebar()

st.title("PlanPilot AI")
st.markdown(
    "Describe a project in a paragraph. The LLM drafts the work breakdown; "
    "the code schedules, checks and simulates it."
)

env = st.selectbox("Environment", list(PRESETS), format_func=lambda e: PRESETS[e].label)
st.caption("Allowed roles: " + ", ".join(PRESETS[env].rates))
brief = st.text_area(
    "Project brief",
    height=160,
    placeholder="What is being delivered, for whom, main features or deliverables, "
    "team size and the target date.",
)
today = date.today()
next_monday = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
c1, c2 = st.columns(2)
start = c1.date_input("Start date", next_monday)
deadline = c2.date_input("Deadline", start + timedelta(weeks=12))

offline = is_offline()
if offline:
    st.info("Offline mode is on: load a frozen demo project from the sidebar.")
if st.button(
    "Generate plan",
    type="primary",
    disabled=offline or not brief.strip() or deadline <= start,
):
    with st.spinner("Drafting the work breakdown and checking it…"):
        try:
            new_project, warnings = plan_chain(llm_client(), env, brief, start, deadline)
            st.session_state["project"] = new_project
            st.session_state["generation"] = {"warnings": warnings, "error": None}
        except LLMError as e:
            st.session_state["generation"] = {"warnings": [], "error": str(e)}
    project = st.session_state.get("project")

gen = st.session_state.get("generation")
if gen and gen["error"]:
    st.error(f"Could not generate a valid plan: {gen['error']}")
elif gen and project is not None:
    st.success(
        f"Generated **{project.name}**: {len(project.tasks)} tasks in "
        f"{len({t.phase for t in project.tasks})} phases. It passed validation and the plan checks."
    )
    for w in gen["warnings"]:
        st.warning(w, icon="⚠️")
    st.page_link("pages/1_Plan.py", label="Open the plan", icon="📋")
elif project is not None:
    st.info(f"Current project: **{project.name}** (demo). Open Plan or Simulation in the sidebar.")
