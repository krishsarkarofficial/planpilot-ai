from datetime import date, timedelta

import streamlit as st

from planpilot.config import PRESETS, llm_available
from planpilot.engine.schedule import check_plan
from planpilot.llm.chains import plan_chain
from planpilot.llm.client import LLMError
from planpilot.samples import load_sample
from planpilot.ui import demo_envs, is_offline, llm_client, load_demo, sidebar

st.set_page_config(page_title="PlanPilot AI", page_icon=":material/flight:", layout="wide")
project = sidebar()

PAGES = [
    (
        "pages/1_Plan.py",
        "Plan",
        ":material/calendar_month:",
        "Work breakdown, critical path, Gantt",
    ),
    ("pages/2_Risks.py", "Risks", ":material/warning:", "Risk register and 5×5 heatmap"),
    ("pages/3_Simulation.py", "Simulation", ":material/casino:", "P50 / P80 / P90 finish and cost"),
    ("pages/4_Execution.py", "Execution", ":material/speed:", "Earned value and status report"),
    ("pages/5_Decide.py", "Decide", ":material/balance:", "Compare options, decision memo"),
]

st.title("PlanPilot AI")
st.subheader("From a project brief to a plan, a risk forecast and a decision")
st.markdown(
    "An LLM drafts the plan. Tested, seeded code schedules it, simulates it and computes every "
    "number you see. **The LLM proposes, the code verifies.**"
)

demo_tab, new_tab = st.tabs(["Try a demo project", "Generate from your brief"])

with demo_tab:
    st.caption("Frozen, validated projects that work offline. Pick one and open any page.")
    envs = demo_envs()
    for col, env in zip(st.columns(len(envs)), envs, strict=True):
        sample = load_sample(env)
        kind, _, what = PRESETS[env].label.partition(" (")
        brief = sample.brief[:110].rsplit(" ", 1)[0] + "…"
        with col.container(border=True, height=300):
            st.markdown(f"**{kind}**: {what.rstrip(')')}")
            st.caption(
                f"{len(sample.tasks)} tasks · {len(sample.risks)} risks · "
                f"deadline {sample.deadline:%d %b %Y}"
            )
            st.write(brief)
            current = project is not None and project.name == sample.name
            if st.button(
                "Loaded: open any page" if current else "Open this demo",
                key=f"demo_{env}",
                type="secondary" if current else "primary",
                width="stretch",
                disabled=current,
            ):
                load_demo(env)
                st.rerun()

with new_tab:
    if not llm_available():
        st.info(
            "Generating a plan needs an LLM API key, and this copy has none, so it runs on the "
            "demo projects. Run it locally with a key to generate your own."
        )
    elif is_offline():
        st.info("Offline mode is on: load a frozen demo project instead.")
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

    if st.button(
        "Generate plan",
        type="primary",
        disabled=is_offline() or not brief.strip() or deadline <= start,
    ):
        with st.spinner("Drafting the work breakdown and checking it…"):
            try:
                st.session_state["project"], _ = plan_chain(
                    llm_client(), env, brief, start, deadline
                )
                st.session_state["generation"] = {"error": None}
            except LLMError as e:
                st.session_state["generation"] = {"error": str(e)}
        project = st.session_state.get("project")

    gen = st.session_state.get("generation")
    if gen and gen["error"]:
        st.error(f"Could not generate a valid plan: {gen['error']}")
    elif gen and project is not None:
        st.success(
            f"Generated **{project.name}**: {len(project.tasks)} tasks in "
            f"{len({t.phase for t in project.tasks})} phases. It passed validation and the "
            "plan checks."
        )
        for w in check_plan(project)[1]:  # live, so it reflects risks added later
            st.warning(w, icon="⚠️")

st.divider()
if project is not None:
    st.markdown(f"#### Current project: {project.name}")
else:
    st.markdown("#### What you get")
for col, (path, label, icon, blurb) in zip(st.columns(len(PAGES)), PAGES, strict=True):
    with col.container(border=True):
        st.page_link(path, label=label, icon=icon)
        st.caption(blurb)

with st.expander("How it works"):
    st.markdown(
        """
- **The LLM drafts:** tasks with three-point estimates and dependencies, risks in
  cause → event → effect form, status reports and decision memos. It is called only when you
  click a button.
- **The code checks and calculates:** every LLM output is parsed into typed models and checked
  (ids, dependencies, cycles, roles, plan plausibility); errors go back to the LLM for a retry.
  The schedule, Monte Carlo forecast, earned value and option ranking come from seeded Python, so
  the same inputs always give the same numbers.
- **The LLM never calculates:** in the status report and the memo it may only narrate figures
  that code computed, and a number that is not in the fact sheet is rejected.
- **Limits:** the demo projects are synthetic, plan quality has no ground truth, and the tool
  supports a decision; a person still makes it.
"""
    )
