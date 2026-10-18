import pytest

from aifw import assessment, specs
from aifw.cli import create_parser, execute
from aifw.common import API, read_yaml, write_yaml
from test_workflows import init

AT = "2026-10-18T00:00:00.000Z"


def requirement(rid, statement, scenario_id, then):
    scenario = dict(id=scenario_id, given=["um usuário cadastrado"], when=["ele age"], then=[then])
    return dict(id=rid, strength="MUST", statement=statement, scenarios=[scenario])


def fake(scores, calls):
    """Probability per scenario outcome text; unknown pairs are covered."""

    def call(model, state, questions):
        calls.append(state)
        return {
            "covers": dict(type="noul", noul=next((v for k, v in scores.items() if k in state), 0.95))
        }, 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(
        assessment=dict(mode="shadow", features=["traceability"]), externalAllowlist=["openrouter"]
    )
    write_yaml(tmp_path / "aifw.yaml", manifest)
    specs.create_change(tmp_path, dict(id="login", title="Login", summary="S", level="L2", createdAt=AT))
    delta = dict(
        apiVersion=API,
        kind="CapabilityDelta",
        changeId="login",
        capability="auth",
        title="Autenticação",
        purpose="Controlar o acesso",
        operations=dict(
            added=[
                requirement(
                    "REQ-LOCK", "Bloquear a conta após 5 senhas erradas", "SCN-LOCK", "a conta fica bloqueada"
                ),
                requirement(
                    "REQ-MAIL",
                    "Enviar e-mail de boas-vindas no cadastro",
                    "SCN-MAIL",
                    "o relatório é exportado",
                ),
            ],
            modified=[],
            removed=[],
        ),
    )
    write_yaml(specs.change_dir(tmp_path, "login") / "specs/auth.delta.yaml", delta)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def test_weak_pairs_are_reported_and_cached(project):
    calls = []
    result = assessment.review_traces(project, "login", call=fake({"relatório é exportado": 0.04}, calls))
    assert result["recorded"] and len(result["pairs"]) == 2 and len(calls) == 2
    assert result["weakTraces"] == [dict(requirement="REQ-MAIL", scenario="SCN-MAIL", probability=0.04)]
    again = assessment.review_traces(project, "login", call=fake({}, calls))
    assert again["status"] == "cached" and len(calls) == 2


def test_spec_analyze_keeps_its_result_and_adds_the_review(project, monkeypatch):
    monkeypatch.setattr(assessment, "decide", fake({"relatório é exportado": 0.04}, []))
    args = create_parser().parse_args(["spec", "analyze", "login", "--json"])
    value, code = execute(args, project)
    assert value["assessment"]["weakTraces"][0]["requirement"] == "REQ-MAIL"
    manifest = read_yaml(project / "aifw.yaml")
    manifest["spec"]["assessment"]["features"] = ["tasks"]
    write_yaml(project / "aifw.yaml", manifest)
    plain, plain_code = execute(args, project)
    assert "assessment" not in plain and plain_code == code
    assert {k: v for k, v in value.items() if k != "assessment"} == plain


def test_traceability_report(project):
    assessment.review_traces(project, "login", call=fake({"relatório é exportado": 0.04}, []))
    assessment.record_verdicts(project, [1], "human:me", feature="traceability")
    text = assessment.render_report(assessment.report(project, "traceability"))
    assert "Rastreabilidade da spec" in text and "REQ-MAIL → SCN-MAIL (4%)" in text
