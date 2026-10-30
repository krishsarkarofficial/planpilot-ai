import hashlib

import pandas as pd
import streamlit as st

from planpilot import viz
from planpilot.config import N_ITERATIONS, WEIGHT_SCENARIOS
from planpilot.engine.decision import (
    BASELINE,
    CRITERIA,
    describe_change,
    normalised_frame,
    suggest_options,
)
from planpilot.engine.montecarlo import SimResult
from planpilot.engine.schedule import finish_date
from planpilot.llm.chains import memo_chain
from planpilot.llm.client import LLMError
from planpilot.memo import RECOMMENDATION_SCENARIO, fmt_metric, memo_facts, template_memo
from planpilot.samples import demo_options
from planpilot.ui import (
    current_seed,
    is_offline,
    llm_client,
    run_comparison,
    run_simulation,
    sidebar,
)

st.set_page_config(page_title="Decide · PlanPilot AI", layout="wide")
project = sidebar()

st.title("Decision: compare options")
if project is None:
    st.info("Load a demo project from the sidebar, or generate one on Home.")
    st.stop()

st.subheader(project.name)
seed = current_seed()
options = demo_options(project)
if options is not None:
    st.caption(
        f"Three hand-written options for this frozen demo project. {N_ITERATIONS:,} runs per "
        f"alternative, seed {seed}, the same random draws for each."
    )
else:
    baseline_sim: SimResult = run_simulation(project, seed)
    options = suggest_options(project, baseline_sim)
    st.caption(
        "Options suggested by code from the baseline simulation: more people on the role with the "
        "most critical work, mitigation of the risks that threaten the critical path, and a later "
        f"deadline. {N_ITERATIONS:,} runs per alternative, seed {seed}."
    )

comparison = run_comparison(project, options, seed)
m = comparison.metrics
winner = comparison.winners[RECOMMENDATION_SCENARIO]

with st.expander("The options", expanded=True):
    for r in comparison.results:
        changes = "; ".join(describe_change(c, project) for c in r.option.changes) or "no change"
        st.markdown(f"**{r.name}**: {r.option.description}  \n:grey[{changes}]")

c1, c2 = st.columns([2, 1])
c1.metric(f"Recommended ({RECOMMENDATION_SCENARIO} weights)", winner)
if comparison.stable:
    c2.badge(
        "Same winner under every weight scenario", icon=":material/check_circle:", color="green"
    )
else:
    c2.badge("The winner depends on the weights", icon=":material/warning:", color="orange")
    c2.caption(" · ".join(f"{s}: {w}" for s, w in comparison.winners.items()))

st.markdown("#### Results per alternative")
rows = []
for r in comparison.results:
    row = m.loc[r.name]
    rows.append(
        {
            "Alternative": r.name,
            "Deadline": f"{r.project.deadline:%d %b %Y}",
            "P50": fmt_metric("p50", row["p50"]),
            "P80": fmt_metric("p80", row["p80"]),
            "P80 finish date": f"{finish_date(r.project, row['p80']):%d %b %Y}",
            "P(meet deadline)": fmt_metric("prob_on_time", row["prob_on_time"]),
            "Expected cost": fmt_metric("cost", row["cost"]),
            "Spread (P90 − P50)": fmt_metric("spread", row["spread"]),
        }
    )
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

left, right = st.columns(2)
with left:
    st.markdown("#### S-curves")
    st.plotly_chart(viz.option_scurves(comparison), width="stretch")
with right:
    st.markdown("#### Weight sensitivity")
    st.plotly_chart(viz.scenario_scores(comparison), width="stretch")

st.markdown("#### Ranking under each weight scenario")
rank = pd.DataFrame(
    {
        s: [
            f"{score[n]:.2f} · #{int(score.rank(ascending=False, method='first')[n])}"
            for n in m.index
        ]
        for s, score in comparison.scores.items()
    },
    index=m.index,
)
rank.columns = [
    f"{s} ({', '.join(f'{w:.2f}' for w in WEIGHT_SCENARIOS[s].values())})" for s in rank.columns
]
st.dataframe(rank, width="stretch")
st.caption(
    "Weights are in the order: " + ", ".join(c.label for c in CRITERIA.values()) + ". "
    "Raw values above; min-max scores below. With so few alternatives, min-max exaggerates "
    "small gaps, so check the raw values."
)
norm = normalised_frame(m).round(2)
norm.columns = [f"{CRITERIA[k].label} (score)" for k in norm.columns]
st.dataframe(norm, width="stretch")

st.markdown("#### Decision memo")
facts = memo_facts(project, comparison, seed)
key = hashlib.sha256(facts.encode("utf-8")).hexdigest()
if st.button("Write the memo with the LLM", disabled=is_offline()):
    with st.spinner("Writing the memo and checking its figures…"):
        try:
            st.session_state["decision_memo"] = {
                "key": key,
                "memo": memo_chain(llm_client(), project, comparison, seed),
                "error": None,
            }
        except LLMError as e:
            st.session_state["decision_memo"] = {"key": key, "memo": None, "error": str(e)}
saved = st.session_state.get("decision_memo")
if saved and saved["key"] == key and saved["error"]:
    st.error(f"Could not write a memo that uses only the given figures: {saved['error']}")
if saved and saved["key"] == key and saved["memo"] is not None:
    memo = saved["memo"]
    st.caption(
        "Narrated by the LLM from the figures below; every number was checked against them "
        "and the recommendation must match the code's ranking."
    )
else:
    memo = template_memo(project, comparison)
    st.caption("Written by code from a template. The LLM button narrates the same figures.")
with st.container(border=True):
    st.markdown(f"**{memo.headline}**")
    st.markdown(memo.situation)
    st.markdown(f"**Recommendation.** {memo.recommendation}")
    left, right = st.columns(2)
    left.markdown("**Why**\n" + "\n".join(f"- {x}" for x in memo.rationale))
    right.markdown("**Trade-offs**\n" + "\n".join(f"- {x}" for x in memo.trade_offs))
    st.markdown(f"**Sensitivity.** {memo.sensitivity}")
    st.markdown("**Next steps**\n" + "\n".join(f"- {x}" for x in memo.next_steps))
with st.expander("Facts given to the LLM"):
    st.code(facts, language=None)

with st.expander("How this was computed"):
    st.markdown(
        f"""
- **Options:** each option is applied to a copy of the project, then the whole project is
  simulated again with the same seed ({seed}). Each task and risk keeps its own random stream,
  so a difference between alternatives comes from the option, not sampling noise. The
  baseline ("{BASELINE}") is ranked too, so doing nothing can win.
- **Add people:** the role's tasks take 1 / (1 + e·k / n) of the time (e = 0.6 efficiency, k
  people added to n now, so more people help less than proportionally). The role is charged
  (1 + k) × its daily rate. Risk delays are not shortened.
- **Cut scope:** the tasks are removed, their dependents take over their predecessors, and
  risks that only affected cut tasks disappear. The value of the cut work is not modelled.
- **Mitigate risks:** the chosen risks' probabilities are multiplied; the one-off cost is added.
- **Extend deadline:** moves the deadline by working days. It costs nothing in this model.
- **Criteria:** P80 finish, probability of meeting the option's own deadline, expected (mean)
  cost and spread (P90 − P50). Each is min-max scaled to 0–1 across the alternatives (1 = best;
  lower-is-better criteria are inverted) and combined with the weights of each scenario.
- **Memo:** code computes every figure and the ranking. The LLM only narrates; a number that
  is not in the fact sheet, an unknown task or risk id, or a recommendation other than the
  {RECOMMENDATION_SCENARIO} winner is sent back as an error and retried (up to 3 attempts).
"""
    )
