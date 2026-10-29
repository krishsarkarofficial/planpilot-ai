import pytest

from planpilot.engine.risks import heatmap_cells, impact_level, probability_level, register_frame
from planpilot.samples import load_sample


@pytest.mark.parametrize(
    "p, level", [(0.05, 1), (0.1, 1), (0.11, 2), (0.3, 2), (0.5, 3), (0.7, 4), (0.71, 5), (0.9, 5)]
)
def test_probability_levels(p, level):
    assert probability_level(p) == level


@pytest.mark.parametrize("d, level", [(0.5, 1), (1, 1), (2, 2), (3, 2), (5, 3), (10, 4), (11, 5)])
def test_impact_levels(d, level):
    assert impact_level(d) == level


def test_register_scores_and_order():
    p = load_sample("software")
    df = register_frame(p)
    assert len(df) == len(p.risks)
    r03 = df.set_index("id").loc["R03"]  # p 0.5 -> 3, impact 3 days -> 2
    assert r03["score"] == 6 and r03["expected_delay"] == pytest.approx(1.5)
    assert list(df["score"]) == sorted(df["score"], reverse=True)


def test_heatmap_cells_cover_every_risk():
    p = load_sample("software")
    cells = heatmap_cells(p)
    assert sorted(i for ids in cells.values() for i in ids) == sorted(r.id for r in p.risks)


def test_empty_register():
    p = load_sample("software").model_copy(update={"risks": []})
    assert register_frame(p).empty and heatmap_cells(p) == {}
