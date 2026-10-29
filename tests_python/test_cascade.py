"""Cascade orchestration: the path comes from the complexity, the risk adds governance (ADR-0042)."""

from pathlib import Path

import pytest
import yaml

from aifw import assessment
from aifw.claude import AGENTS, check_project, enable_project
from test_workflows import init

CASCADE = {
    "FAST": ("trivial", "aifw-quick (Haiku, low) planeja e executa sozinho"),
    "WORK": ("simples", "aifw-executor (Sonnet, medium) planeja e executa sozinho"),
    "PLANNED": ("moderada", "aifw-planner (Sonnet, high) planeja"),
    "CRITICAL": ("alta", "o agente principal (Opus) planeja e divide entre um ou mais aifw-lead"),
}
WORDS = {"L0": "baixo", "L1": "médio", "L2": "alto", "L3": "crítico"}


def context(path, final="L0", model_risk=None):
    return assessment.path_context(
        dict(
            status="recorded",
            risk=dict(value=model_risk or final),
            finalRisk=final,
            importance=dict(value="média"),
            complexity=dict(value=CASCADE[path][0]),
            path=path,
        )
    )


@pytest.mark.parametrize("path", CASCADE)
def test_each_path_names_its_cascade(path):
    text = context(path)
    assert f"caminho {path}" in text and CASCADE[path][1] in text
    assert "O agente principal só orquestra" in text


@pytest.mark.parametrize("final", ["L2", "L3"])
@pytest.mark.parametrize(
    ("path", "alone"),
    [
        ("FAST", "aifw-executor (Sonnet) planeja e executa sozinho"),
        ("WORK", "aifw-senior (Opus) planeja e executa sozinho"),
    ],
)
def test_high_risk_on_a_small_task_swaps_the_cascade(path, alone, final):
    text = context(path, final)
    assert alone in text and "aifw-adversary e aifw-qa revisam" in text and WORDS[final] in text
    assert "sem revisor" not in text and CASCADE[path][1] not in text


@pytest.mark.parametrize("path", ["PLANNED", "CRITICAL"])
def test_high_risk_keeps_the_cascade_on_larger_tasks(path):
    assert "sozinho" not in context(path, "L3")


@pytest.mark.parametrize("path", CASCADE)
@pytest.mark.parametrize("final", ["L0", "L1", "L2", "L3"])
def test_governance_follows_the_risk(path, final):
    text = context(path, final)
    assert f"risco {WORDS[final]} ({final})" in text
    assert ("aifw spec request-approval" in text) == (final in {"L2", "L3"})
    if final in {"L0", "L1"}:
        assert "revisam" not in text


def test_diff_raised_risk_is_shown():
    assert "elevado pelo diff" in context("FAST", "L2", model_risk="L0")


def meta(root, name):
    text = (Path(root) / f".claude/agents/{name}.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---")[1])


def test_new_templates_and_enable(tmp_path):
    init(tmp_path)
    enable_project(tmp_path)
    for name, model, effort in [
        ("aifw-planner", "sonnet", "high"),
        ("aifw-lead", "sonnet", "medium"),
        ("aifw-worker", "haiku", "medium"),
        ("aifw-senior", "opus", "high"),
    ]:
        data = meta(tmp_path, name)
        assert (data["model"], data["effort"]) == (model, effort)
        if name in {"aifw-planner", "aifw-lead"}:
            assert "tools" not in data and "Agent" not in data.get("disallowedTools", "")
        else:
            assert data["disallowedTools"] == "Agent" and "tools" not in data
    assert len(AGENTS) == 9
    assert not any("subagent" in f for f in check_project(tmp_path, tmp_path / "home")["findings"])
