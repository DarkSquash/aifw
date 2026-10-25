"""Reviewer subagents cannot change the project; role-subagent files are control files (ADR-0038)."""

from pathlib import Path

import pytest
import yaml

from aifw.hooks import handle
from test_workflows import init

REVIEWERS = ("aifw-adversary", "aifw-qa")
TEMPLATES = Path(__file__).resolve().parent.parent / "templates/claude"
REVIEW = ".aifw/changes/active/x/independent-review.md"

DENIED = [
    ("Edit", dict(file_path="{root}/python/aifw/claude.py", old_string="a", new_string="b")),
    ("Bash", dict(command="sed -i 's/a/b/' python/aifw/claude.py")),
    ("Bash", dict(command="git commit -m x")),
    ("Bash", dict(command="git stash")),
    ("Bash", dict(command="git stash -a")),
    ("Bash", dict(command="git tag -a v9 -m x")),
    ("Bash", dict(command="git reflog expire --expire=now --all")),
    ("Bash", dict(command="echo x > notes.txt")),
    ("Bash", dict(command="cp a b")),
    ("Bash", dict(command="touch x")),
    ("Bash", dict(command="mkdir x")),
    ("Bash", dict(command="tee x")),
    ("Bash", dict(command="git branch -r -d origin/x")),
    ("Bash", dict(command="git tag -l -d v1")),
]
ALLOWED = [
    ("Write", dict(file_path="{root}/" + REVIEW, content="x")),
    ("Write", dict(file_path="{outside}/probe.py", content="x")),
    ("Bash", dict(command="python -m pytest tests_python -q")),
    ("Bash", dict(command="git diff main...HEAD")),
    ("Bash", dict(command="git branch -a")),
    ("Bash", dict(command="git stash list")),
    ("Bash", dict(command="git tag -l")),
    ("Bash", dict(command="git tag -v v1")),
    ("Bash", dict(command="git config list")),
    ("Bash", dict(command="git config get user.name")),
    ("Bash", dict(command="git remote get-url origin")),
    ("Bash", dict(command="python --version")),
    ("Bash", dict(command="python -m ruff check python")),
    ("Bash", dict(command="cmp a b")),
    ("Bash", dict(command="git reflog")),
    ("Bash", dict(command="aifw spec analyze x")),
]


@pytest.fixture
def project(tmp_path):
    init(tmp_path)
    return tmp_path


def decide(root, tool, tool_input, agent_type=None, outside=None):
    tool_input = {
        k: v.format(root=root, outside=outside) if isinstance(v, str) else v for k, v in tool_input.items()
    }
    payload = dict(cwd=str(root), session_id="s", tool_name=tool, tool_input=tool_input)
    if agent_type:
        payload["agent_type"] = agent_type
    output = handle(payload)
    return output and output["hookSpecificOutput"]


@pytest.mark.parametrize("agent", REVIEWERS)
@pytest.mark.parametrize("tool,tool_input", DENIED)
def test_reviewer_cannot_change_the_project(project, agent, tool, tool_input):
    out = decide(project, tool, tool_input, agent)
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].startswith("AIFW: a reviewer subagent")


@pytest.mark.parametrize("agent", REVIEWERS)
@pytest.mark.parametrize("tool,tool_input", ALLOWED)
def test_reviewer_can_review_and_probe(project, tmp_path_factory, agent, tool, tool_input):
    outside = tmp_path_factory.mktemp("probe")
    out = decide(project, tool, tool_input, agent, outside)
    assert out is None or out["permissionDecision"] != "deny"


def test_reviewer_lock_holds_when_the_policy_fails(project, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("broken policy")

    monkeypatch.setattr("aifw.hooks.evaluate", broken)
    out = decide(project, "Bash", dict(command="git commit -m x"), "aifw-qa")
    assert out["permissionDecision"] == "deny"
    assert "reviewer subagent" in out["permissionDecisionReason"]


@pytest.mark.parametrize("agent", [None, "aifw-executor"])
@pytest.mark.parametrize("tool,tool_input", DENIED)
def test_other_agents_are_not_held_by_the_reviewer_lock(project, agent, tool, tool_input):
    out = decide(project, tool, tool_input, agent)
    assert out is None or "reviewer subagent" not in out["permissionDecisionReason"]


@pytest.mark.parametrize(
    "tool,tool_input",
    [
        ("Edit", dict(file_path="{root}/.claude/agents/aifw-qa.md", old_string="a", new_string="b")),
        ("Bash", dict(command="sed -i 's/a/b/' .claude/agents/aifw-qa.md")),
    ],
)
def test_subagent_files_are_control_files(project, tool, tool_input):
    out = decide(project, tool, tool_input)
    assert out["permissionDecision"] == "ask"
    assert ".claude/agents/aifw-" in out["permissionDecisionReason"]


@pytest.mark.parametrize(
    "tool,tool_input",
    [
        ("Bash", dict(command="aifw claude enable")),
        ("Edit", dict(file_path="{root}/.claude/agents/minha.md", old_string="a", new_string="b")),
    ],
)
def test_other_calls_do_not_touch_the_control_file_rule(project, tool, tool_input):
    out = decide(project, tool, tool_input)
    assert out is None or ".claude/agents/aifw-" not in out["permissionDecisionReason"]


def meta_and_text(name):
    text = (TEMPLATES / "agents" / f"{name}.md").read_text(encoding="utf-8")
    tools = yaml.safe_load(text.split("---")[1])["tools"]
    return [t.strip() for t in tools.split(",")], text


def test_reviewer_templates():
    adversary_tools, adversary = meta_and_text("aifw-adversary")
    qa_tools, qa = meta_and_text("aifw-qa")
    assert "Agent" not in adversary_tools + qa_tools
    assert "Skill" not in adversary_tools
    assert "eixo Spec" in adversary
    assert "eixo Standards" in qa
    skill = (TEMPLATES / "skills/aifw-workflow/SKILL.md").read_text(encoding="utf-8")
    assert "eixo Spec" in skill and "eixo Standards" in skill
