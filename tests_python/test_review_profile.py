"""Review profile: light interface/text changes get one reviewer, the aifw-qa (ADR-0046)."""

from pathlib import Path

import pytest

from aifw import assessment, gates
from aifw.claude import enable_project
from test_workflows import init

TEMPLATES = Path(__file__).resolve().parent.parent / "templates/claude"
SKILL = "skills/aifw-workflow/SKILL.md"
QA = "agents/aifw-qa.md"
NOTICE = "Perfil de revisão interface ou texto"
COMPLEXITY = {"FAST": "trivial", "WORK": "simples", "PLANNED": "moderada", "CRITICAL": "alta"}


def context(path, final):
    return assessment.path_context(
        dict(
            status="recorded",
            risk=dict(value=final),
            finalRisk=final,
            importance=dict(value="média"),
            complexity=dict(value=COMPLEXITY[path]),
            path=path,
        )
    )


def template(name):
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["PLANNED", "CRITICAL"])
@pytest.mark.parametrize("final", ["L0", "L1"])
def test_notice_on_larger_tasks_with_low_or_medium_risk(path, final):
    assert NOTICE in context(path, final)


@pytest.mark.parametrize("path", ["PLANNED", "CRITICAL"])
@pytest.mark.parametrize("final", ["L2", "L3"])
def test_no_notice_on_high_risk(path, final):
    assert NOTICE not in context(path, final)


@pytest.mark.parametrize("path", ["FAST", "WORK"])
@pytest.mark.parametrize("final", ["L0", "L1", "L2", "L3"])
def test_no_notice_on_small_tasks(path, final):
    assert NOTICE not in context(path, final)


def test_skill_template_declares_the_profile():
    text = template(SKILL)
    for phrase in (
        "Perfil de revisão: completo",
        "Na dúvida",
        "risco alto ou crítico",
        "devolve sem",
        "o `aifw-qa` faz os dois",
        "uma só nos perfis leves",
    ):
        assert phrase in text, phrase


def test_qa_template_covers_the_light_profile():
    text = template(QA)
    for phrase in (
        "Perfil de revisão: interface",
        "eixo Spec",
        "não escreva a linha",
        "ferramenta Skill",
        "declarado no chat",
    ):
        assert phrase in text, phrase
    tools = next(line for line in text.splitlines() if line.startswith("tools:"))
    names = [name.strip() for name in tools.removeprefix("tools:").split(",")]
    assert "Skill" in names and "Agent" not in names


def test_adversary_template_ignores_profiles():
    assert "Perfil" not in template("agents/aifw-adversary.md")


@pytest.mark.parametrize("name", ["impeccable", "design-taste-frontend", "ui-ux-pro-max", "shadcn"])
def test_templates_do_not_name_front_end_skills(name):
    assert name not in template(SKILL) and name not in template(QA)


def test_installed_copies_carry_the_profile(tmp_path):
    init(tmp_path)
    enable_project(tmp_path)
    skill = (tmp_path / ".claude/skills/aifw-workflow/SKILL.md").read_text(encoding="utf-8")
    qa = (tmp_path / ".claude/agents/aifw-qa.md").read_text(encoding="utf-8")
    assert "Perfil de revisão: completo" in skill
    assert "Perfil de revisão: interface" in qa


def test_gate_accepts_a_single_qa_section(tmp_path):
    review = tmp_path / "independent-review.md"
    review.write_text(
        "## QA\n\nPerfil de revisão: texto, declarado no chat.\n\nResultado: aprovado\n", encoding="utf-8"
    )
    assert gates.review_result(tmp_path, "independent-review.md")["status"] == "pass"
    review.write_text("## QA\n\nPerfil de revisão: texto, declarado no chat.\n", encoding="utf-8")
    assert gates.review_result(tmp_path, "independent-review.md")["status"] == "fail"
