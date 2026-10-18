import pytest

from aifw import assessment
from aifw.cli import create_parser, execute
from aifw.common import read_yaml, write_yaml
from aifw.intake import set_charter_field
from test_workflows import init


def fake(choices, confidence=0.9):
    """Answer per driver prompt fragment; other drivers get `unknown`."""

    def call(model, state, questions):
        question = questions["driver"]
        choice = next((v for k, v in choices.items() if k in question["instructions"]), "unknown")
        return {"driver": dict(type="choice", choice=choice, confidence=confidence)}, 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(
        assessment=dict(mode="shadow", features=["decisions"]), externalAllowlist=["openrouter"]
    )
    write_yaml(tmp_path / "aifw.yaml", manifest)
    set_charter_field(tmp_path, "problem", "Loja virtual de uma única equipe pequena, lançada de uma vez")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


TOPOLOGY = {
    "independent deployment": "deployment:together",
    "operate distributed": "operations:limited",
    "transactional consistency": "consistency:transactional",
}


def test_suggests_confident_signals_and_shows_their_ranking(project):
    result = assessment.suggest_signals(project, "system-topology", "primeira versão", call=fake(TOPOLOGY))
    assert result["recorded"]
    assert result["suggestedSignals"] == [
        "consistency:transactional",
        "deployment:together",
        "operations:limited",
    ]
    assert result["answers"]["domain-boundaries"]["signal"] == "unknown"
    assert result["ranking"][0]["optionId"] in {"monolith", "modular-monolith"}
    assert result["context"] == "primeira versão"


def test_low_confidence_answers_are_not_suggested(project):
    result = assessment.suggest_signals(project, "system-topology", call=fake(TOPOLOGY, confidence=0.4))
    assert result["suggestedSignals"] == []


def test_official_ranking_ignores_suggestions(project, monkeypatch):
    monkeypatch.setattr(assessment, "decide", fake(TOPOLOGY))
    args = ["decision", "recommend", "--category", "system-topology", "--json"]
    plain, _ = execute(create_parser().parse_args(args), project)
    suggested, _ = execute(create_parser().parse_args([*args, "--suggest-signals"]), project)
    assert "assessment" not in plain and suggested["assessment"]["suggestedSignals"]
    assert {k: v for k, v in suggested.items() if k != "assessment"} == plain
    assert plain["signals"] == []


def test_feature_toggle_and_report(project):
    assessment.suggest_signals(project, "system-topology", call=fake(TOPOLOGY))
    assessment.record_verdicts(project, [1], "human:me", value="wrong", feature="decisions")
    text = assessment.render_report(assessment.report(project, "decisions"))
    assert "Catálogos de decisão" in text and "deployment:together" in text and "wrong" in text
    manifest = read_yaml(project / "aifw.yaml")
    manifest["spec"]["assessment"]["features"] = ["tasks"]
    write_yaml(project / "aifw.yaml", manifest)
    off = assessment.suggest_signals(project, "system-topology", call=fake(TOPOLOGY))
    assert off["status"] == "unavailable" and "decisions" in off["reason"]
