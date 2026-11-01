"""The task assessor is always active when the tasks feature is on (ADR-0036, ADR-0037)."""

import pytest

from aifw import assessment
from aifw.assessment import active, assess, record_verdicts
from aifw.claude import check_project, enable_project
from aifw.cli import create_parser
from aifw.common import AifwError, read_json, write_json
from aifw.hooks import handle
from test_assessment import fake, set_spec
from test_workflows import init


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    set_spec(tmp_path, assessment=dict(mode="shadow"), externalAllowlist=["openrouter"])
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def prompt(root, text):
    return handle(dict(cwd=str(root), hook_event_name="UserPromptSubmit", session_id="s", prompt=text))


def use(monkeypatch, risk="L2", importance="média", complexity="alta"):
    answer = fake(risk, importance, complexity)
    monkeypatch.setattr(
        assessment, "decide", lambda m, task, qs: ({k: answer(m, task, k)[0] for k in qs}, 0.0)
    )


def test_the_path_reaches_the_agent_without_any_activation(project, monkeypatch):
    use(monkeypatch)
    assert active(project)
    text = prompt(project, "Reescrever a busca do app para aceitar erros de digitação")
    context = text["hookSpecificOutput"]["additionalContext"]
    assert "caminho CRITICAL" in context and "aifw-lead" in context and "aifw-worker" in context
    assert assessment.read_lines(project / assessment.SHADOW_LOG)[-1]["mode"] == "active"
    assert prompt(project, "sim pode") is None  # short replies are not requests


def test_turning_the_assessment_off_turns_the_path_off(project, monkeypatch):
    use(monkeypatch)
    set_spec(project, assessment=dict(mode="off"))
    assert not active(project)
    assert prompt(project, "Reescrever a busca do app para aceitar erros de digitação") is None


@pytest.mark.parametrize(
    "broken",
    [
        lambda *_: (_ for _ in ()).throw(AifwError("NOT_READY", "Decision model unavailable: offline")),
        lambda *_: ({}, 0.0),  # a malformed answer: KeyError
    ],
)
def test_any_failure_reaches_the_agent_as_a_notice(project, monkeypatch, broken):
    monkeypatch.setattr(assessment, "decide", broken)
    text = prompt(project, "Adicionar paginação na listagem de mudanças")["hookSpecificOutput"]
    assert (
        "indisponível" in text["additionalContext"] and "classificação de sempre" in text["additionalContext"]
    )


def test_delegating_to_haiku_is_the_agents_call(project, monkeypatch):
    use(monkeypatch)
    prompt(project, "Reescrever a busca do app para aceitar erros de digitação")
    payload = dict(cwd=str(project), tool_name="Agent", session_id="s", tool_input=dict(model="haiku"))
    assert handle(payload) is None


def test_verdicts_stay_as_quality_tracking(project):
    for _ in range(3):
        assess(project, "tarefa", call=fake())
    record_verdicts(project, [1, 2, 3], "human:me")
    assert active(project)


def test_the_prompt_hook_waits_for_the_agent(project):
    old = {"type": "command", "command": "aifw-hook || true", "shell": "bash", "timeout": 60, "async": True}
    judge = dict(matcher="Bash", hooks=[dict(type="command", command="aifw assess judge --hook || true")])
    settings = dict(hooks=dict(UserPromptSubmit=[dict(hooks=[old])], PreToolUse=[judge]))
    write_json(project / ".claude/settings.json", settings)
    assert any("UserPromptSubmit" in f for f in check_project(project)["findings"])
    enable_project(project)
    hooks = read_json(project / ".claude/settings.json")["hooks"]
    hook = hooks["UserPromptSubmit"][0]["hooks"][0]
    assert "async" not in hook and hook["timeout"] == 60
    assert "assess judge" not in str(hooks["PreToolUse"])  # the removed judge hook is cleaned up
    assert not any("hook " in f for f in check_project(project)["findings"])


def test_there_is_no_activation_command():
    with pytest.raises(AifwError):
        create_parser().parse_args(["assess", "activate", "--by", "human:me"])
