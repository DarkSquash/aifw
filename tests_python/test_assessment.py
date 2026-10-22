import json
import subprocess

import pytest

from aifw import assessment
from aifw.assessment import COMPLEXITY, IMPORTANCE, assess, path_for, record_verdicts, render_report, report
from aifw.cli import create_parser, execute
from aifw.common import AifwError, read_yaml, write_yaml
from aifw.hooks import handle
from test_hardening import GIT
from test_workflows import init


def fake(risk="L1", importance="média", complexity="simples"):
    def call(model, task, key):
        if key == "risk":
            return dict(choice=risk, confidence=0.9), 0.00001
        names, value = (IMPORTANCE, importance) if key == "importance" else (COMPLEXITY, complexity)
        probabilities = {name: 0.97 if name == value else 0.01 for name in names}
        return dict(score=float(names.index(value)), probabilities=probabilities), 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(assessment=dict(mode="shadow"), externalAllowlist=["openrouter"])
    write_yaml(tmp_path / "aifw.yaml", manifest)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def set_spec(root, **values):
    manifest = read_yaml(root / "aifw.yaml")
    manifest["spec"].update(values)
    write_yaml(root / "aifw.yaml", manifest)


def test_assessor_stays_off_until_every_guard_passes(project, monkeypatch, tmp_path_factory):
    plain = tmp_path_factory.mktemp("plain")
    init(plain)
    assert "off" in assess(plain, "x", call=fake())["reason"]
    set_spec(project, externalAllowlist=[])
    assert "openrouter" in assess(project, "x", call=fake())["reason"]
    set_spec(project, externalAllowlist=["openrouter"], dataClassification="confidential")
    assert "confidential" in assess(project, "x", call=fake())["reason"]
    set_spec(project, dataClassification="internal")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    result = assess(project, "x", call=fake())
    assert result["status"] == "unavailable" and not (project / assessment.SHADOW_LOG).exists()


@pytest.mark.parametrize(
    ("risk", "importance", "complexity", "path"),
    [
        ("L0", "baixa", "trivial", "FAST"),
        ("L0", "média", "simples", "FAST"),
        ("L0", "crítica", "simples", "WORK"),
        ("L0", "média", "moderada", "WORK"),
        ("L1", "baixa", "trivial", "WORK"),
        ("L1", "média", "alta", "PLANNED"),
        ("L2", "baixa", "simples", "PLANNED"),
        ("L3", "média", "simples", "CRITICAL"),
    ],
)
def test_path_rule(risk, importance, complexity, path):
    assert path_for(risk, importance, complexity) == path


def test_records_in_shadow_and_the_diff_sets_a_risk_floor(project):
    first = assess(project, "Corrigir texto do README", call=fake("L0", "baixa", "trivial"))
    assert first["recorded"] and first["id"] == 1 and first["path"] == "FAST"
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(GIT + ["add", "-A"], cwd=project, check=True)
    subprocess.run(GIT + ["commit", "-qm", "base"], cwd=project, check=True)
    (project / "src/auth").mkdir(parents=True)
    (project / "src/auth/login.py").write_text("x = 1\n")
    second = assess(project, "Ajuste trivial", use_diff=True, call=fake("L0", "baixa", "trivial"))
    assert second["risk"]["value"] == "L0" and second["floor"]["level"] == "L2"
    assert second["finalRisk"] == "L2" and second["path"] == "PLANNED" and second["id"] == 2


def test_verdicts_feed_the_report_and_the_activation_criteria(project):
    for risk in ("L0", "L1", "L1"):
        assess(project, f"tarefa {risk}", call=fake(risk))
    record_verdicts(project, [1, 2], "human:me")
    record_verdicts(project, [3], "human:me", value="CRITICAL", note="mexe em produção")
    summary = report(project)["summary"]
    assert summary["judged"] == 3 and summary["agreement"] == pytest.approx(0.667, abs=0.001)
    assert summary["criticalDemoted"] == [3] and not summary["criteriaMet"]
    text = render_report(report(project))
    assert "| 1 | tarefa L0 |" in text and "concorda" in text and "CRITICAL" in text
    with pytest.raises(AifwError):
        record_verdicts(project, [9], "human:me")


def test_report_skips_automatic_messages_recorded_before_the_filter(project):
    assess(project, '<agent-message from="a1"> relatório do subagente revisor', call=fake(), source="prompt")
    assess(project, "Adicionar paginação na listagem de mudanças", call=fake(), source="prompt")
    rows = report(project)["rows"]
    assert [r["id"] for r in rows] == [2] and report(project)["summary"]["assessments"] == 1


def test_criteria_met_after_fifty_agreeing_verdicts(project):
    for _ in range(50):
        assess(project, "tarefa", call=fake())
    record_verdicts(project, list(range(1, 51)), "human:me")
    assert report(project)["summary"]["criteriaMet"]


def test_verdicts_are_human_approvals(project):
    assess(project, "tarefa", call=fake())
    args = create_parser().parse_args(["assess", "verdict", "--id", "1", "--agree", "--by", "human:me"])
    with pytest.raises(AifwError) as error:
        execute(args, project)
    assert error.value.code == "APPROVAL_REQUIRED"
    payload = dict(
        cwd=str(project),
        tool_name="Bash",
        tool_input=dict(command="aifw assess verdict --id 1 --agree --by human:me"),
    )
    assert handle(payload)["hookSpecificOutput"]["permissionDecision"] == "deny"
    edit = dict(
        cwd=str(project), tool_name="Edit", tool_input=dict(file_path=".aifw/assessments/verdicts.jsonl")
    )
    assert handle(edit)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_session_start_announces_the_report_at_fifty(project):
    log = project / assessment.SHADOW_LOG
    log.parent.mkdir(parents=True)
    entry = dict(id=0, task="t", path="WORK", risk=dict(value="L1", confidence=1.0), cost=0)
    log.write_text("".join(json.dumps(dict(entry, id=i)) + "\n" for i in range(1, 51)), encoding="utf-8")
    start = handle(dict(cwd=str(project), hook_event_name="SessionStart", session_id="s"))
    assert "aifw assess report" in start["hookSpecificOutput"]["additionalContext"]


def test_service_failure_is_reported_not_recorded(project, monkeypatch):
    def broken(*_, **__):
        raise OSError("offline")

    monkeypatch.setattr(assessment.urllib.request, "urlopen", broken)
    monkeypatch.setattr(assessment.time, "sleep", lambda _: None)
    with pytest.raises(AifwError):
        assess(project, "tarefa")
    assert not (project / assessment.SHADOW_LOG).exists()


def test_each_request_is_assessed_in_the_background(project, monkeypatch):
    answer = fake("L2", "alta", "moderada")
    monkeypatch.setattr(
        assessment, "decide", lambda m, task, qs: ({k: answer(m, task, k)[0] for k in qs}, 0.0)
    )

    def prompt(text):
        return handle(dict(cwd=str(project), hook_event_name="UserPromptSubmit", session_id="s", prompt=text))

    automatic = (
        '<agent-message from="a1"> [Subagent hand-back] O relatório final da revisão',
        "<system-reminder> The session you started finished a turn and reported",
        "<task-notification> <task-id>b1</task-id> <status>completed</status> mais texto",
        '<cross-session-message from="local_1"> Pronto, rodei o gerador da referência',
        "Background (from the session that started this one): o AIFW é o framework",
        "Stop hook feedback: AIFW: code changed after the last successful verification",
    )
    for text in ("pode subir", "/ponytail lite", "sim pode fazer isso", *automatic):
        assert prompt(text) is None
    assert not (project / assessment.SHADOW_LOG).exists()
    assert prompt("Reescrever a busca do app com api_key=abc123 para aceitar erros de digitação") is None
    (record,) = [json.loads(line) for line in (project / assessment.SHADOW_LOG).read_text().splitlines()]
    assert record["source"] == "prompt" and record["path"] and "abc123" not in record["task"]
    set_spec(project, assessment=dict(mode="shadow", features=["impasse"]))
    prompt("Outra tarefa longa o bastante para avaliar")
    assert len((project / assessment.SHADOW_LOG).read_text().splitlines()) == 1
