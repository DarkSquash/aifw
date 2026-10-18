import pytest

from aifw import assessment
from aifw.common import read_yaml, write_yaml
from aifw.impasse import create_impasse_case, record_attempt
from test_workflows import AT, init


def attempt(n, hypothesis, intervention):
    return dict(
        id=f"attempt-{n}",
        hypothesis=hypothesis,
        intervention=intervention,
        evidence=["log.txt"],
        outcome="failure",
        occurredAt=AT,
    )


def fake(probability):
    def call(model, state, questions):
        assert "Tentativa anterior" in state and "Nova tentativa" in state
        return {"same": dict(type="noul", noul=probability)}, 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(
        assessment=dict(mode="shadow", features=["tasks", "impasse"]), externalAllowlist=["openrouter"]
    )
    write_yaml(tmp_path / "aifw.yaml", manifest)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def case_with_one_attempt():
    case = create_impasse_case("login", "L1")
    return record_attempt(case, attempt(1, "cache stale", "clear the cache"))


def test_paraphrase_is_flagged_without_changing_the_case(project):
    case = case_with_one_attempt()
    new = attempt(2, "the cache is outdated", "wipe the cached data")
    result = assessment.compare_attempt(project, case, new, call=fake(0.9))
    assert result["recorded"] and result["wouldRepeat"] and not result["exactRepeat"]
    assert result["comparisons"] == [dict(attempt="attempt-1", probability=0.9)]
    assert len(case["attempts"]) == 1  # shadow mode never touches the case


def test_distinct_attempt_and_threshold(project):
    case = case_with_one_attempt()
    new = attempt(2, "token expired", "refresh the token")
    assert not assessment.compare_attempt(project, case, new, call=fake(0.69))["wouldRepeat"]
    assert assessment.compare_attempt(project, case, new, call=fake(0.7))["wouldRepeat"]


def test_exact_repeat_is_reported(project):
    case = case_with_one_attempt()
    same = attempt(2, "Cache  STALE", "clear the cache")
    assert assessment.compare_attempt(project, case, same, call=fake(1.0))["exactRepeat"]


def test_feature_toggle_and_first_attempt(project):
    first = create_impasse_case("login", "L1")
    assert assessment.compare_attempt(project, first, attempt(1, "a", "b"), call=fake(1))["status"] == (
        "nothing-to-compare"
    )
    manifest = read_yaml(project / "aifw.yaml")
    manifest["spec"]["assessment"]["features"] = ["tasks"]
    write_yaml(project / "aifw.yaml", manifest)
    result = assessment.compare_attempt(project, case_with_one_attempt(), attempt(2, "a", "b"), call=fake(1))
    assert result["status"] == "unavailable" and "impasse" in result["reason"]


def test_impasse_report_and_verdicts(project):
    case = case_with_one_attempt()
    assessment.compare_attempt(project, case, attempt(2, "x", "y"), call=fake(0.95))
    assessment.compare_attempt(project, case, attempt(3, "z", "w"), call=fake(0.1))
    assessment.record_verdicts(project, [1], "human:me", feature="impasse")
    assessment.record_verdicts(project, [2], "human:me", value="repeat", feature="impasse")
    value = assessment.report(project, "impasse")
    assert value["summary"]["judged"] == 2 and value["summary"]["agreement"] == 0.5
    text = assessment.render_report(value)
    assert "Impasse: tentativa repetida" in text and "| 1 | login |" in text
    with pytest.raises(Exception):
        assessment.record_verdicts(project, [1], "human:me", value="CRITICAL", feature="impasse")


def test_notice_per_feature_at_fifty(project):
    case = case_with_one_attempt()
    for n in range(50):
        assessment.compare_attempt(project, case, attempt(n + 2, f"h{n}", f"i{n}"), call=fake(0.2))
    notices = assessment.pending_notices(project)
    assert len(notices) == 1 and "--feature impasse" in notices[0]
