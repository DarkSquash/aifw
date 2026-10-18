import pytest

from aifw import assessment
from aifw.cli import create_parser, execute
from aifw.common import read_yaml, write_yaml
from aifw.intake import set_charter_field
from test_workflows import init


def fake(levels, calls):
    """Level per prompt fragment; anything else is specific."""

    def call(model, state, questions):
        calls.append(state)
        level = next((v for k, v in levels.items() if k in state), "específica")
        probabilities = {name: 0.96 if name == level else 0.02 for name in assessment.SPECIFICITY}
        return {"specific": dict(type="score", probabilities=probabilities)}, 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(
        assessment=dict(mode="shadow", features=["intake"]), externalAllowlist=["openrouter"]
    )
    write_yaml(tmp_path / "aifw.yaml", manifest)
    set_charter_field(tmp_path, "problem", "a definir")
    set_charter_field(tmp_path, "audiences", ["lojistas com até 5 funcionários que vendem pelo Instagram"])
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def charter(root):
    return read_yaml(root / ".aifw/charter.yaml")


def test_vague_answers_become_weak_and_only_answered_fields_are_judged(project):
    calls = []
    result = assessment.review_intake(project, charter(project), call=fake({"a definir": "vaga"}, calls))
    assert result["recorded"] and len(calls) == 2  # outcomes and scope are still empty
    assert result["levels"] == {"problem": "vaga", "audiences": "específica"}
    assert [w["field"] for w in result["weakAnswers"]] == ["problem"]
    assert result["weakAnswers"][0]["prompt"].startswith("Qual problema")


def test_unchanged_charter_is_cached(project):
    calls = []
    assessment.review_intake(project, charter(project), call=fake({}, calls))
    again = assessment.review_intake(project, charter(project), call=fake({}, calls))
    assert again["status"] == "cached" and len(calls) == 2
    set_charter_field(project, "problem", "Reduzir de 3 dias para 1 hora o tempo de resposta a pedidos")
    changed = assessment.review_intake(project, charter(project), call=fake({}, calls))
    assert changed["recorded"] and changed["id"] == 2


def test_intake_status_never_depends_on_the_assessment(project, monkeypatch):
    monkeypatch.setattr(assessment, "decide", fake({"a definir": "vaga"}, []))
    args = create_parser().parse_args(["intake", "status", "--json"])
    value, code = execute(args, project)
    assert value["assessment"]["weakAnswers"][0]["field"] == "problem"
    monkeypatch.delenv("OPENROUTER_API_KEY")
    without, code_without = execute(args, project)
    assert without["assessment"]["status"] == "unavailable" and code_without == code
    assert {k: v for k, v in without.items() if k != "assessment"} == {
        k: v for k, v in value.items() if k != "assessment"
    }


def test_intake_report_and_verdicts(project):
    assessment.review_intake(project, charter(project), call=fake({"a definir": "vaga"}, []))
    assessment.record_verdicts(project, [1], "human:me", feature="intake")
    value = assessment.report(project, "intake")
    assert value["summary"]["agreement"] == 1
    text = assessment.render_report(value)
    assert "Intake: respostas do Charter" in text and "problem: vaga" in text
