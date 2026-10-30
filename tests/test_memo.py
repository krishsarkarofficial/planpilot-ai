import pytest
from test_llm import FakeTransport

from planpilot.engine.decision import BASELINE, compare
from planpilot.llm.chains import memo_chain
from planpilot.llm.client import LLMClient
from planpilot.memo import DecisionMemo, memo_facts, memo_text, template_memo
from planpilot.samples import available_samples, load_options, load_sample
from planpilot.status import unknown_numbers

PROJECT = load_sample("software")
COMPARISON = compare(PROJECT, load_options("software"))
FACTS = memo_facts(PROJECT, COMPARISON, 42)
TEMPLATE = template_memo(PROJECT, COMPARISON)
WINNER = COMPARISON.winners["balanced"]


def test_facts_carry_every_alternative_and_the_ranking():
    for name in COMPARISON.metrics.index:
        assert name in FACTS
    assert f"winner: {WINNER}" in FACTS and "Same winner under every scenario:" in FACTS
    assert "Change against the baseline" in FACTS


@pytest.mark.parametrize("env", available_samples())
def test_template_memo_uses_only_facts_and_the_code_ranking(env):
    project = load_sample(env)
    comparison = compare(project, load_options(env))
    memo = template_memo(project, comparison)
    assert memo.recommended_option == comparison.winners["balanced"]
    assert unknown_numbers(memo_text(memo), memo_facts(project, comparison, 42)) == []


def test_memo_chain_retries_invented_figure_and_overridden_ranking(tmp_path):
    invented = TEMPLATE.model_copy(update={"situation": "There is a 12.5% chance of delay."})
    other = next(n for n in COMPARISON.metrics.index if n != WINNER)
    overridden = TEMPLATE.model_copy(update={"recommended_option": other})
    t = FakeTransport(
        invented.model_dump_json(), overridden.model_dump_json(), TEMPLATE.model_dump_json()
    )
    memo = memo_chain(
        LLMClient(transport=t, cache_dir=tmp_path, offline=False), PROJECT, COMPARISON, 42
    )
    assert isinstance(memo, DecisionMemo) and memo == TEMPLATE
    assert len(t.calls) == 3
    assert "figure 12.5 is not in the facts" in t.calls[1][1]
    assert f"recommended_option must be exactly '{WINNER}'" in t.calls[2][1]
    assert f"winner: {WINNER}" in t.calls[0][1]  # the prompt carries the precomputed ranking


def test_baseline_can_win_and_the_memo_says_so():
    comparison = compare(PROJECT, [], n=200)  # no options: doing nothing is the only choice
    assert comparison.winners["balanced"] == BASELINE
    memo = template_memo(PROJECT, comparison)
    assert memo.recommended_option == BASELINE and memo.next_steps
