"""With an approved change active the main session delegates edits to subagents (ADR-0040)."""

import pytest

from aifw.common import AifwError, read_yaml, write_yaml
from aifw.hooks import handle
from aifw.permissions import load_permission_policy
from test_approved_scope import add_change
from test_workflows import init

ALL = ["python/aifw/claude.py", "python/aifw/hooks.py", "docs/"]


@pytest.fixture
def project(tmp_path):
    init(tmp_path)
    set_orchestration(tmp_path, dict(mode="required", sessionPaths=["python/aifw/hooks.py"]))
    return tmp_path


def set_orchestration(root, orchestration):
    file = root / ".aifw/permissions.yaml"
    policy = read_yaml(file)
    policy["orchestration"] = orchestration
    write_yaml(file, policy)


def edit(root, path, tool="Edit", agent_id=None):
    tool_input = dict(file_path=str(root / path), old_string="a", new_string="b", content="x")
    payload = dict(cwd=str(root), session_id="s", tool_name=tool, tool_input=tool_input)
    if agent_id:
        payload["agent_id"] = agent_id
    output = handle(payload)
    return output and output["hookSpecificOutput"]


def test_the_session_is_denied_and_told_who_to_delegate_to(project):
    add_change(project, "plan", paths=ALL)
    for tool in ("Edit", "Write"):
        out = edit(project, "python/aifw/claude.py", tool=tool)
        assert out["permissionDecision"] == "deny"
        reason = out["permissionDecisionReason"]
        assert "orchestrated" in reason and "aifw-executor" in reason and "aifw-quick" in reason


def test_a_subagent_is_not_denied(project):
    add_change(project, "plan", paths=ALL)
    assert edit(project, "python/aifw/claude.py", agent_id="sub") is None


def test_session_paths_change_folders_and_outside_files_are_free(project, tmp_path_factory):
    add_change(project, "plan", paths=ALL)
    assert edit(project, "python/aifw/hooks.py") is None
    assert edit(project, ".aifw/changes/active/plan/evidence/tests.txt") is None
    outside = tmp_path_factory.mktemp("probe") / "probe.py"
    assert edit(project, outside, tool="Write") is None


def test_without_an_approved_change_the_session_edits(project):
    assert edit(project, "python/aifw/claude.py") is None
    add_change(project, "draft", approved=False, paths=ALL)
    assert edit(project, "python/aifw/claude.py") is None


def test_mode_off(project):
    add_change(project, "plan", paths=ALL)
    set_orchestration(project, dict(mode="off"))
    assert edit(project, "python/aifw/claude.py") is None


def test_every_approved_change_is_named(project):
    add_change(project, "plan", paths=ALL)
    add_change(project, "other", paths=ALL)
    reason = edit(project, "python/aifw/claude.py")["permissionDecisionReason"]
    assert "other, plan" in reason


def test_a_broken_change_is_left_out(project):
    folder = add_change(project, "plan", paths=ALL)
    (folder / "tasks.yaml").write_text("tasks: [", encoding="utf-8")
    assert edit(project, "python/aifw/claude.py") is None


def test_the_schema_rejects_an_unknown_mode(project):
    set_orchestration(project, dict(mode="x"))
    with pytest.raises(AifwError):
        load_permission_policy(project)
