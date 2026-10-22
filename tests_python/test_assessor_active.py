"""Active mode of the task assessor (ADR-0036): a human activation, then the path reaches the agent."""

import pytest

from aifw import assessment
from aifw.assessment import activate, active, assess, record_verdicts, report
from aifw.claude import check_project, enable_project
from aifw.cli import create_parser, execute
from aifw.common import AifwError, read_json, read_yaml, write_yaml
from aifw.hooks import handle
from test_assessment import fake, set_spec
from test_hardening import commit
from test_workflows import init

AT = "2026-10-22T00:00:00Z"


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    set_spec(tmp_path, assessment=dict(mode="shadow"), externalAllowlist=["openrouter"])
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def judged(root, count=50, call=None):
    for _ in range(count):
        assess(root, "tarefa", call=call or fake())
    record_verdicts(root, list(range(1, count + 1)), "human:me")


def prompt(root, text, session="s"):
    return handle(dict(cwd=str(root), hook_event_name="UserPromptSubmit", session_id=session, prompt=text))


def use(monkeypatch, risk="L2", importance="média", complexity="alta"):
    answer = fake(risk, importance, complexity)
    monkeypatch.setattr(
        assessment, "decide", lambda m, task, qs: ({k: answer(m, task, k)[0] for k in qs}, 0.0)
    )


def test_activation_waits_for_the_criteria(project):
    judged(project, 30)
    with pytest.raises(AifwError) as error:
        activate(project, "tasks", "human:me", AT)
    assert error.value.code == "APPROVAL_REQUIRED" and any("50 needed" in d for d in error.value.details)
    assert not (project / assessment.ACTIVATION_FILE).exists() and not active(project)


def test_activation_needs_agreement_and_no_demoted_critical(project):
    judged(project, 50)
    record_verdicts(project, [1], "human:me", value="CRITICAL")
    with pytest.raises(AifwError) as error:
        activate(project, "tasks", "human:me", AT)
    assert any("CRITICAL" in d for d in error.value.details)


def test_activation_is_a_human_approval(project):
    judged(project)
    args = create_parser().parse_args(["assess", "activate", "--by", "human:me"])
    with pytest.raises(AifwError) as error:
        execute(args, project)
    assert error.value.code == "APPROVAL_REQUIRED"
    command = dict(command="aifw assess activate --feature tasks --by human:me")
    output = handle(dict(cwd=str(project), tool_name="Bash", tool_input=command))
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    edit = dict(file_path=".aifw/assessor.yaml")
    output = handle(dict(cwd=str(project), tool_name="Write", tool_input=edit))
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_active_mode_hands_the_path_to_the_agent(project, monkeypatch):
    judged(project)
    use(monkeypatch)
    assert prompt(project, "Reescrever a busca do app para aceitar erros de digitação") is None  # shadow
    activate(project, "tasks", "human:me", AT)
    assert active(project) and report(project)["summary"]["active"]
    context = prompt(project, "Reescrever a busca do app para aceitar erros de digitação")
    text = context["hookSpecificOutput"]["additionalContext"]
    assert "caminho PLANNED" in text and "Opus planeja" in text
    last = assessment.read_lines(project / assessment.SHADOW_LOG)[-1]
    assert last["mode"] == "active" and last["session"] == "s"
    assert prompt(project, "sim pode") is None  # short replies are not requests


def test_service_failure_only_says_so(project, monkeypatch):
    judged(project)
    activate(project, "tasks", "human:me", AT)

    def broken(*_):
        raise AifwError("NOT_READY", "Decision model unavailable: offline")

    monkeypatch.setattr(assessment, "decide", broken)
    text = prompt(project, "Adicionar paginação na listagem de mudanças")["hookSpecificOutput"]
    assert (
        "indisponível" in text["additionalContext"] and "classificação de sempre" in text["additionalContext"]
    )


def test_haiku_asks_after_a_planned_path_in_this_session(project, monkeypatch):
    judged(project)
    activate(project, "tasks", "human:me", AT)

    def delegate(session):
        payload = dict(
            cwd=str(project), tool_name="Agent", session_id=session, tool_input=dict(model="haiku")
        )
        return handle(payload)

    use(monkeypatch, "L0", "baixa", "trivial")
    prompt(project, "Corrigir o texto de ajuda do comando runs show", session="a")
    assert delegate("a") is None
    use(monkeypatch, "L2")
    prompt(project, "Reescrever a busca do app para aceitar erros de digitação", session="a")
    assert delegate("a")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert delegate("other") is None


def test_unsigned_activation_does_not_count(project):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    policy = read_yaml(project / ".aifw/permissions.yaml")
    policy["approvals"] = dict(requireSignedCommit=True)
    write_yaml(project / ".aifw/permissions.yaml", policy)
    commit(project)
    assert not active(project)


def test_turning_the_assessment_off_turns_active_mode_off(project):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    set_spec(project, assessment=dict(mode="off"))
    assert not active(project)


def test_enable_installs_a_waiting_prompt_hook_only_when_active(project):
    def prompt_hook():
        settings = read_json(project / ".claude/settings.json")
        return settings["hooks"]["UserPromptSubmit"][0]["hooks"][0]

    enable_project(project)
    assert prompt_hook()["async"] is True
    judged(project)
    activate(project, "tasks", "human:me", AT)
    assert any("UserPromptSubmit" in f for f in check_project(project)["findings"])
    enable_project(project)
    assert "async" not in prompt_hook()
    assert not any("UserPromptSubmit" in f for f in check_project(project)["findings"])


def test_agreement_below_ninety_percent_refuses_even_when_it_rounds_up(project):
    # 188 of 209 is 89.95%: report() shows 0.9 after rounding, but the criterion is not met.
    judged(project, 209)
    record_verdicts(project, list(range(1, 22)), "human:me", value="FAST")
    with pytest.raises(AifwError) as error:
        activate(project, "tasks", "human:me", AT)
    assert error.value.code == "APPROVAL_REQUIRED"


def test_a_new_model_needs_a_new_activation(project):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    set_spec(project, assessment=dict(mode="shadow", model="perplexity/pplx-decider-v2"))
    assert not active(project)


def test_any_failure_reaches_the_agent_as_a_notice(project, monkeypatch):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    monkeypatch.setattr(assessment, "decide", lambda *_: ({}, 0.0))  # a malformed answer: KeyError
    text = prompt(project, "Adicionar paginação na listagem de mudanças")["hookSpecificOutput"]
    assert "indisponível" in text["additionalContext"]


def test_a_corrupted_log_does_not_make_every_delegation_ask(project):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    with (project / assessment.SHADOW_LOG).open("a", encoding="utf-8") as log:
        log.write("{not json\n")
    payload = dict(cwd=str(project), tool_name="Agent", session_id="s", tool_input=dict(model="haiku"))
    assert handle(payload) is None


def test_session_start_says_when_active_mode_is_on(project):
    judged(project)
    activate(project, "tasks", "human:me", AT)
    start = handle(dict(cwd=str(project), hook_event_name="SessionStart", session_id="s"))
    assert "is active" in start["hookSpecificOutput"]["additionalContext"]


def test_session_start_tells_when_activation_is_possible(project):
    judged(project)
    start = handle(dict(cwd=str(project), hook_event_name="SessionStart", session_id="s"))
    assert "aifw assess activate" in start["hookSpecificOutput"]["additionalContext"]
