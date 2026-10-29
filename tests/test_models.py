import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from planpilot.models import Option, Project, Task

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample" / "software.json"


def sample_data() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_frozen_software_project_validates():
    p = Project.model_validate(sample_data())
    assert 15 <= len(p.tasks) <= 22
    assert 8 <= len(p.risks) <= 10


def test_cycle_rejected():
    data = sample_data()
    data["tasks"][0]["depends_on"] = ["T19"]  # T01 -> ... -> T19 -> T01
    with pytest.raises(ValidationError, match="cycle"):
        Project.model_validate(data)


def test_bad_dependency_id_rejected():
    data = sample_data()
    data["tasks"][1]["depends_on"] = ["T99"]
    with pytest.raises(ValidationError, match="unknown task T99"):
        Project.model_validate(data)


def test_self_dependency_rejected():
    data = sample_data()
    data["tasks"][1]["depends_on"] = ["T02"]
    with pytest.raises(ValidationError, match="depends on itself"):
        Project.model_validate(data)


def test_duplicate_task_id_rejected():
    data = sample_data()
    data["tasks"][1]["id"] = "T01"
    with pytest.raises(ValidationError, match="duplicate task ids"):
        Project.model_validate(data)


def test_unknown_role_rejected():
    data = sample_data()
    data["tasks"][0]["role"] = "mason"
    with pytest.raises(ValidationError, match="role 'mason'"):
        Project.model_validate(data)


def test_risk_with_unknown_task_rejected():
    data = sample_data()
    data["risks"][0]["affected_task_ids"] = ["T50"]
    with pytest.raises(ValidationError, match="unknown task T50"):
        Project.model_validate(data)


def test_optimistic_above_most_likely_rejected():
    with pytest.raises(ValidationError, match="optimistic <= most_likely"):
        Task(id="T01", name="x", phase="A", role="pm", optimistic=5, most_likely=3, pessimistic=8)


def test_option_change_types_parse():
    opt = Option.model_validate(
        {
            "name": "Add developer",
            "description": "One more developer",
            "changes": [
                {"type": "add_resource", "role": "developer", "added_people": 1},
                {"type": "extend_deadline", "days": 5},
            ],
        }
    )
    assert opt.changes[0].efficiency == 0.6
    assert opt.changes[1].type == "extend_deadline"
