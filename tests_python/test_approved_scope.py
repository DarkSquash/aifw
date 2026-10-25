"""Edits stay inside the approved plan's paths; the approved tasks.yaml is a control file (ADR-0039)."""

import pytest

from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from test_workflows import init

PATHS = ["python/aifw/claude.py", "docs/", "templates/claude/agents/*.md"]


@pytest.fixture
def project(tmp_path):
    init(tmp_path)
    return tmp_path


def add_change(root, change_id, approved=True, paths=PATHS):
    folder = root / ".aifw/changes/active" / change_id
    folder.mkdir(parents=True)
    change = dict(metadata=dict(id=change_id), status="draft")
    if approved:
        change["approval"] = dict(approvedBy="human:x", approvedAt="2026-10-25T00:00:00Z", record="x")
    write_yaml(folder / "change.yaml", change)
    write_yaml(folder / "tasks.yaml", dict(changeId=change_id, tasks=[dict(id="TASK-X", paths=paths)]))
    return folder


def edit(root, path, tool="Edit"):
    tool_input = dict(file_path=str(root / path), old_string="a", new_string="b", content="x")
    output = handle(dict(cwd=str(root), session_id="s", tool_name=tool, tool_input=tool_input))
    return output and output["hookSpecificOutput"]


@pytest.mark.parametrize(
    "path",
    [
        "python/aifw/claude.py",
        "docs/x.md",
        "docs/deep/y.md",
        "templates/claude/agents/aifw-qa.md",
        ".aifw/changes/active/plan/evidence/tests.txt",
        ".aifw/changes/active/other/proposal.md",
    ],
)
def test_planned_paths_and_change_folders_do_not_ask(project, path):
    add_change(project, "plan")
    assert edit(project, path) is None


def test_edit_outside_the_plan_asks(project):
    add_change(project, "plan")
    out = edit(project, "python/aifw/hooks.py")
    assert out["permissionDecision"] == "ask"
    assert "outside the approved plan of plan" in out["permissionDecisionReason"]
    assert edit(project, "python/aifw/hooks.py", tool="Write")["permissionDecision"] == "ask"


def test_without_an_approved_change_nothing_asks(project):
    assert edit(project, "python/aifw/hooks.py") is None
    add_change(project, "draft", approved=False)
    assert edit(project, "python/aifw/hooks.py") is None
    assert edit(project, ".aifw/changes/active/draft/tasks.yaml") is None


def test_change_scope_off(project):
    add_change(project, "plan")
    policy_file = project / ".aifw/permissions.yaml"
    policy = read_yaml(policy_file)
    policy["changeScope"] = "off"
    write_yaml(policy_file, policy)
    assert edit(project, "python/aifw/hooks.py") is None


def test_paths_of_every_approved_change_count(project):
    add_change(project, "plan")
    add_change(project, "other", paths=["python/aifw/hooks.py"])
    assert edit(project, "python/aifw/hooks.py") is None
    assert "approved plan of other, plan" in edit(project, "README.md")["permissionDecisionReason"]


def test_the_approved_plan_is_a_control_file(project):
    add_change(project, "plan")
    out = edit(project, ".aifw/changes/active/plan/tasks.yaml")
    assert out["permissionDecision"] == "ask"
    assert "control file tasks.yaml" in out["permissionDecisionReason"]
    command = "sed -i 's/a/b/' .aifw/changes/active/plan/tasks.yaml"
    shell = handle(dict(cwd=str(project), session_id="s", tool_name="Bash", tool_input=dict(command=command)))
    assert "control file tasks.yaml" in shell["hookSpecificOutput"]["permissionDecisionReason"]


def test_a_broken_change_is_left_out(project):
    folder = add_change(project, "plan")
    (folder / "tasks.yaml").write_text("tasks: [", encoding="utf-8")
    assert edit(project, "python/aifw/hooks.py") is None


def test_files_outside_the_project_do_not_ask(project, tmp_path_factory):
    add_change(project, "plan")
    outside = tmp_path_factory.mktemp("probe") / "probe.py"  # absolute, so project / outside is outside
    assert edit(project, outside, tool="Write") is None
