import json
from datetime import date

import pytest

from planpilot.llm.chains import plan_chain
from planpilot.llm.client import (
    DailyQuotaExceeded,
    LLMClient,
    LLMError,
    OfflineError,
    extract_json,
)
from planpilot.samples import load_sample

SAMPLE = load_sample("software")
VALID = json.dumps({"name": SAMPLE.name, "tasks": [t.model_dump() for t in SAMPLE.tasks]})
BAD_DEP = VALID.replace('"depends_on": ["T18"]', '"depends_on": ["T99"]')


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, provider: str, prompt: str, temperature: float) -> str:
        self.calls.append((provider, prompt))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def run(client: LLMClient, use_cache: bool = True):
    return plan_chain(
        client, "software", SAMPLE.brief, SAMPLE.start_date, SAMPLE.deadline, use_cache=use_cache
    )


def test_invalid_json_then_valid_retries_with_error(tmp_path):
    t = FakeTransport("not json at all", VALID)
    project, warnings = run(LLMClient(transport=t, cache_dir=tmp_path, offline=False))
    assert len(t.calls) == 2
    assert "rejected by the validator" in t.calls[1][1]
    assert len(project.tasks) == 19 and "only one start task" in warnings[0]


def test_unknown_dependency_is_retried(tmp_path):
    assert BAD_DEP != VALID
    t = FakeTransport(BAD_DEP, VALID)
    run(LLMClient(transport=t, cache_dir=tmp_path, offline=False))
    assert len(t.calls) == 2 and "T99" in t.calls[1][1]


def test_gives_up_after_three_attempts(tmp_path):
    t = FakeTransport("x", "y", "z")
    with pytest.raises(LLMError, match="3 attempts"):
        run(LLMClient(transport=t, cache_dir=tmp_path, offline=False))
    assert len(t.calls) == 3


def test_cache_hit_and_use_cache_false_bypasses(tmp_path):
    t = FakeTransport(VALID, VALID)
    client = LLMClient(transport=t, cache_dir=tmp_path, offline=False)
    run(client)
    run(client)  # cache hit: no new call
    assert len(t.calls) == 1 and len(list(tmp_path.iterdir())) == 1

    for f in tmp_path.iterdir():
        f.unlink()
    run(client, use_cache=False)
    assert len(t.calls) == 2  # transport called
    assert list(tmp_path.iterdir()) == []  # and nothing written


def test_offline_never_touches_network(tmp_path, monkeypatch):
    import openai

    def boom(*a, **k):
        raise AssertionError("network client constructed in offline mode")

    monkeypatch.setattr(openai, "OpenAI", boom)
    t = FakeTransport(VALID)
    with pytest.raises(OfflineError):
        run(LLMClient(transport=t, cache_dir=tmp_path, offline=True))
    with pytest.raises(OfflineError):
        run(LLMClient(cache_dir=tmp_path, offline=True))  # default transport
    assert t.calls == []


def test_daily_quota_switches_to_gemini(tmp_path):
    t = FakeTransport(DailyQuotaExceeded("groq: tokens per day (TPD)"), VALID)
    client = LLMClient(transport=t, cache_dir=tmp_path, offline=False)
    run(client)
    assert [p for p, _ in t.calls] == ["groq", "gemini"]
    assert client.provider == "gemini"


def test_extract_json_strips_fences():
    assert json.loads(extract_json('Here you go:\n```json\n{"a": 1}\n```')) == {"a": 1}


def test_assembled_project_uses_user_inputs(tmp_path):
    t = FakeTransport(VALID)
    project, _ = plan_chain(
        LLMClient(transport=t, cache_dir=tmp_path, offline=False),
        "software", "brief", date(2027, 2, 1), date(2027, 4, 30),
    )  # fmt: skip
    assert project.start_date == date(2027, 2, 1) and project.risks == []
